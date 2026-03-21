# Barlow Automation

Slack 기반 AI 티켓 자동화 시스템.
개발자가 Slack 슬래시 커맨드로 개발 요청을 입력하면 AI가 GitHub 코드를 분석하여
**feat / refactor / fix** 유형의 GitHub 이슈를 자동 생성한다.

---

## 사용 흐름

```
/feat, /refactor, /fix 입력
  → Modal 팝업 (요청 내용 입력)
  → AI가 GitHub 코드 분석 → 관련 이슈 탐색
  → 사용자에게 관련 이슈 목록 + 관계 선택 요청
  → 이슈 초안 생성 → 사용자 확인
  → GitHub 이슈 생성 (관계 설정 포함)
```

### 이슈 관계 옵션

| 선택 | 동작 |
|------|------|
| `reject_duplicate` | 중복으로 판단, 이슈 생성 안 함 |
| `extend_existing` | 신규 이슈를 anchor의 sub-issue(child)로 생성 |
| `block_existing` | 신규 이슈가 anchor를 blocking (anchor는 blocked by 신규 이슈) |
| `create_new_independent` | 독립 이슈로 생성 |

---

## 아키텍처

```
Slack
  │ slash command / modal submit / button click
  ▼
barlow-slack-ack (Lambda Function URL, 29초)
  │ Slack 서명 검증 (Bolt)
  │ SQS 메시지 전송 후 즉시 ack
  ▼
barlow-queue (SQS, batch size=1)
  ▼
barlow-automation-worker (Lambda SQS trigger, 900초)
  │ 워크플로우 step graph 실행
  │ DynamoDB read/write
  │ Slack API 호출
  │ GitHub REST API 호출
  ▼
DynamoDB (3개 테이블)
```

Slack은 이벤트 수신 후 3초 이내 응답을 요구하므로 Lambda를 두 개로 분리한다.

Worker Lambda는 SQS 메시지 1개당 1회 실행된다.
하나의 워크플로우는 사용자 입력이 필요한 WAIT 구간마다 Lambda 실행이 분리되므로,
완료까지 최소 2~3회 실행된다:

```
Lambda 실행 #1 (pipeline_start)
  find_relevant_bc → find_relevant_issue → wait_issue_decision
  → Slack 버튼 전송 후 종료 (DynamoDB에 WAITING 상태 저장)

Lambda 실행 #2 (extend_existing / block_existing / create_new_independent)
  generate_issue_draft → wait_confirmation
  → Slack 초안 전송 후 종료

Lambda 실행 #3 (accept)
  create_github_issue → 완료
```

AI agent가 연속으로 실행되는 #1 단계가 가장 오래 걸리며 최대 15분 타임아웃이 적용된다.

---

## 워크플로우 Step Graph (feat_issue)

```
find_relevant_bc       (Agent: 관련 바운디드 컨텍스트 탐색)
  ↓
find_relevant_issue    (Agent: 기존 이슈 관련성 분석)
  ↓
wait_issue_decision    (UI: 관련 이슈 목록 + 관계 선택 버튼)
  ├─ reject_duplicate      → reject_end (종료)
  ├─ extend_existing       → generate_issue_draft
  ├─ block_existing        → generate_issue_draft
  └─ create_new_independent → generate_issue_draft
  ↓
generate_issue_draft   (Agent: 이슈 초안 생성)
  ↓
wait_confirmation      (UI: 초안 확인 + 수락/재요청 버튼)
  ├─ accept   → create_github_issue
  └─ reject   → regenerate_issue_draft → wait_confirmation (반복)
  ↓
create_github_issue    (GitHub REST API: 이슈 생성 + 관계 설정)
```

---

## 슬래시 커맨드

| 커맨드 | 동작 |
|--------|------|
| `/feat` | 기능 요청 이슈 생성 워크플로우 시작 |
| `/refactor` | 리팩토링 이슈 생성 워크플로우 시작 |
| `/fix` | 버그 수정 이슈 생성 워크플로우 시작 |
| `/drop` | 진행 중인 워크플로우 취소 |

채널+유저 단위로 한 번에 하나의 워크플로우만 활성화된다.
이미 진행 중인 워크플로우가 있으면 새 시작 요청을 거부한다.

---

## 패키지 구조

```
src/
├── config.py                        # 환경변수 기반 Config
├── logging_config.py                # 로깅 초기화
├── local_server.py                  # 로컬 개발용 Socket Mode 서버
│
├── controller/                      # Ack Lambda 진입점
│   ├── lambda_ack.py                # Lambda handler
│   ├── app.py                       # AsyncApp 팩토리
│   ├── router.py                    # 핸들러 등록
│   ├── handler/
│   │   └── slash.py                 # 슬래시 커맨드 + Modal + Block Action 핸들러
│   └── modal_templates/             # /feat, /refactor, /fix Modal 입력 파싱
│
├── app/                             # Worker Lambda 진입점
│   ├── workflow_runtime.py          # Step graph 실행 오케스트레이터
│   ├── handlers/
│   │   └── step_worker_handler.py   # Lambda handler (SQS trigger)
│   └── slack/
│       └── payload_mapper.py        # Slack Block Kit 빌더
│
├── domain/
│   ├── queue.py                     # IQueueSender 인터페이스
│   ├── common/
│   │   ├── models/
│   │   │   ├── lifecycle.py         # WorkflowStatus, StepStatus
│   │   │   ├── step_result.py       # ControlSignal (CONTINUE/WAIT/STOP)
│   │   │   ├── workflow_instance.py # WorkflowInstance + IWorkflowInstanceRepository
│   │   │   └── issue_base.py        # BaseIssueTemplate, IssueType, Label
│   │   ├── ports/
│   │   │   ├── idempotency.py       # IIdempotencyRepository
│   │   │   └── active_session.py    # IActiveSessionRepository
│   │   └── steps/base.py            # Step Protocol
│   │
│   ├── feat/                        # Feature 워크플로우 (완전 구현)
│   │   ├── definition.py            # GRAPH, FIRST_STEP, RESUME_MAP
│   │   ├── executor.py              # FeatAgentExecutor (Agent 팩토리)
│   │   ├── models/
│   │   │   ├── state.py             # FeatIssueWorkflowState
│   │   │   ├── issue.py             # FeatTemplate
│   │   │   └── issue_decision.py    # Decision enum
│   │   ├── steps/                   # 각 step 구현체
│   │   └── agents/                  # Agent 프롬프트 + 출력 스키마
│   │
│   ├── refactor/                    # Refactor 워크플로우 (플레이스홀더)
│   └── fix/                         # Fix 워크플로우 (플레이스홀더)
│
├── agent/
│   ├── base.py                      # IAgent 인터페이스, AgentResult
│   ├── openai.py                    # OpenAIAgent (OpenAI Agents SDK 래퍼)
│   ├── mcp.py                       # GitHubMCPFactory
│   ├── models.py                    # Model 레지스트리 (Claude/GPT 가격표)
│   └── usage.py                     # AgentUsage (토큰 추적)
│
└── infrastructure/
    ├── queue/sqs_publisher.py       # SqsQueueSender (IQueueSender 구현)
    └── storage/
        ├── dynamodb/                # DynamoDB 구현체 (prod)
        └── memory/                  # In-memory 구현체 (로컬 개발)
```

---

## DynamoDB 테이블

### barlow-workflow

워크플로우 인스턴스 저장. WAIT 구간마다 상태를 저장하고 다음 Lambda 실행에서 복원한다.

| 속성 | 타입 | 설명 |
|------|------|------|
| `workflow_id` (PK) | String | UUID |
| `workflow_type` | String | `feat_issue` \| `refactor_issue` \| `fix_issue` |
| `status` | String | `CREATED` \| `RUNNING` \| `WAITING` \| `COMPLETED` \| `CANCELLED` \| `FAILED` |
| `current_step` | String | 현재 실행 중인 step 이름 |
| `state` | Map | 워크플로우 상태 (step별 input/output 누적) |
| `pending_action_token` | String | 사용자 응답 대기 토큰 |
| `slack_channel_id` | String | |
| `slack_user_id` | String | |
| `slack_message_ts` | String | Slack 메시지 업데이트용 타임스탬프 |
| `created_at` | Number | Unix timestamp |
| `ttl` | Number | Unix timestamp (생성 시 +24h, DynamoDB TTL) |

**state 필드 구조 (FeatIssueWorkflowState):**

| 필드 | 타입 | 설명 |
|------|------|------|
| `user_message` | str | 사용자 원본 요청 |
| `bc_candidates` | str \| None | find_relevant_bc 출력 |
| `relevant_issues` | str \| None | find_relevant_issue 출력 (JSON) |
| `issue_decision` | str \| None | 사용자 선택 (Decision enum value) |
| `issue_draft` | str \| None | 생성된 이슈 초안 (FeatTemplate JSON) |
| `github_issue_url` | str \| None | 생성된 GitHub 이슈 URL |
| `user_feedback` | str \| None | 재요청 시 사용자 피드백 |
| `dropped_item_ids` | list[str] | 제외된 항목 ID 목록 |

---

### barlow-pending-action

SQS 이벤트 중복 처리 방지. `attribute_not_exists(pk)` 조건부 PutItem으로 동일 이벤트의 병렬 처리를 차단한다.

| 속성 | 타입 | 설명 |
|------|------|------|
| `pk` (PK) | String | dedup_id (Slack view_id 또는 action_ts) |
| `status` | String | `PROCESSING` \| `DONE` |
| `ttl` | Number | Unix timestamp (생성 시 +1h) |

---

### barlow-active-session

채널+유저 단위 활성 워크플로우 추적. 동일 사용자가 같은 채널에서 워크플로우를 중복 시작하지 못하게 막는다.

| 속성 | 타입 | 설명 |
|------|------|------|
| `pk` (PK) | String | `{channel_id}#{user_id}` |
| `workflow_id` | String | 현재 활성 워크플로우 ID |
| `ttl` | Number | Unix timestamp (생성 시 +24h) |

---

## 이슈 타입

`IssueType` (`src.domain.common.models.issue_base`) 을 단일 소스로 사용한다.

| Enum | GitHub type 값 | Label |
|------|---------------|-------|
| `IssueType.FEAT` | `Feature` | `feat` |
| `IssueType.REFACTOR` | `Refactor` | `refactor` |
| `IssueType.FIX` | `Bug` | `fix` |

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 언어 | Python 3.12+ |
| Slack | Slack Bolt Async (HTTP Mode) |
| AI | OpenAI Agents SDK + Claude (MCP) |
| GitHub | GitHub REST API + GitHub MCP |
| AWS | Lambda × 2, SQS, DynamoDB |
| 배포 | GitHub Actions → S3 → Lambda |

---

## 환경 변수

| 변수명 | 설명 | Lambda |
|--------|------|--------|
| `SLACK_BOT_TOKEN` | Slack Bot OAuth 토큰 (`xoxb-...`) | Ack + Worker |
| `SLACK_SIGNING_SECRET` | Slack 앱 서명 시크릿 | Ack + Worker |
| `SQS_QUEUE_URL` | SQS 큐 URL | Ack + Worker |
| `GITHUB_TOKEN` | GitHub PAT | Ack + Worker |
| `TARGET_REPO` | 분석 대상 저장소 (`owner/repo` 또는 URL) | Ack + Worker |
| `OPENAI_API_KEY` | OpenAI API 키 | Worker |
| `ANTHROPIC_API_KEY` | Anthropic API 키 | Worker |
| `SLACK_APP_TOKEN` | Socket Mode 토큰 (`xapp-...`) | 로컬 개발 전용 |

운영 환경에서는 AWS SSM Parameter Store에 저장하고 Terraform이 Lambda 환경변수로 주입한다.

---

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (default.env 참고)
cp default.env .env

# Socket Mode로 실행
python -m src.local_server
```

---

## 배포

인프라 설계 및 배포 가이드는 별도 문서를 참고한다.

- [infra.md](infra.md) — Terraform 작성자용 리소스 설계 문서
- [.github/workflows/deploy.yml](.github/workflows/deploy.yml) — GitHub Actions 배포 워크플로우
