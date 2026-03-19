# Barlow Automation — 현재 구조 문서

> 최종 업데이트: 2026-03-18

---

## 시스템 개요

Slack 기반 AI 티켓 자동화 시스템. 개발자가 Slack 슬래시 커맨드로 요청하면 AI가 GitHub 코드를 분석하여 개발 티켓을 자동 생성한다.

```
개발자 → /feat "[기능 설명]" → Slack
                                  ↓ Lambda Function URL (Ack Lambda)
                               Bolt App (3초 내 ack)
                                  ↓ SQS 메시지
                               Worker Lambda
                                  ↓ WorkflowRuntime
                               GitHub 이슈 생성
```

---

## 패키지 구조

```
src/
├── config.py                          # 환경변수 기반 설정
├── logging_config.py                  # 로깅 초기화
├── lambda_worker.py                   # Worker Lambda 진입점 (step_worker_handler 위임)
├── local_server.py                    # 로컬 개발용 Socket Mode 서버
│
├── app/                               # 애플리케이션 핸들러
│   └── handlers/
│       └── step_worker_handler.py     # SQS 이벤트 → WorkflowRuntime 위임
│
├── controller/                        # Ack Lambda — Slack 이벤트 수신
│   ├── lambda_ack.py                  # Lambda Function URL 진입점
│   ├── app.py                         # Bolt AsyncApp 팩토리
│   ├── router.py                      # 핸들러 등록
│   ├── _reply.py                      # Slack Block Kit 빌더 (레거시, 로컬 호환용)
│   ├── issue_drop.py                  # 드롭 로직 (droppable_items, drop_items)
│   ├── handler/
│   │   └── slash.py                   # 슬래시커맨드 + 버튼 + 모달 핸들러
│   └── modal_templates/               # 슬래시커맨드별 Modal 정의
│       ├── feat_modal_input.py
│       ├── refactor_modal_input.py
│       └── fix_modal_input.py
│
├── domain/                            # 도메인 인터페이스 및 모델
│   ├── issue/
│   │   └── entities.py                # 이슈 템플릿 모델 (Label, FeatTemplate 등)
│   ├── issue_templates.py             # re-export 래퍼 (하위 호환)
│   ├── idempotency.py                 # IIdempotencyRepository 인터페이스
│   └── queue.py                       # IQueueSender 인터페이스
│
├── agent/                             # Agent 실행 레이어
│   ├── agent_info.py                  # AvailableAgents enum (프롬프트 + 스키마)
│   ├── base.py                        # IAgent, AgentResult
│   ├── usage.py                       # AgentUsage (토큰/비용 추적)
│   ├── mcp.py                         # GitHubMCPFactory (MCP 서버 관리)
│   ├── models.py                      # Model.GPT 레지스트리
│   └── openai.py                      # OpenAIAgent 구현체
│
├── workflow/                          # Workflow Runtime 아키텍처 (현재 사용)
│   ├── models/
│   │   ├── lifecycle.py               # WorkflowStatus, StepStatus Enum
│   │   ├── step_result.py             # StepResult (step 실행 결과 계약)
│   │   ├── workflow_instance.py       # WorkflowInstance (핵심 엔티티)
│   │   └── workflow_state.py          # FeatIssueWorkflowState (step 간 shared state)
│   ├── runtime/
│   │   └── workflow_runtime.py        # WorkflowRuntime (start/resume/_execute_until_wait)
│   ├── agents/                        # Agent 자산 (prompt/schema/adapter 분리)
│   │   ├── relevant_bc_finder/
│   │   ├── feat_issue_generator/
│   │   └── feat_issue_regenerator/
│   ├── executors/
│   │   └── agent_executor.py          # AgentKey + AgentExecutor.build()
│   ├── steps/
│   │   ├── common/
│   │   │   └── wait_issue_confirmation_step.py  # 이슈 초안 Slack 전송 후 대기
│   │   └── feat_issue/
│   │       ├── find_relevant_bc_step.py
│   │       ├── generate_issue_draft_step.py
│   │       ├── regenerate_issue_draft_step.py
│   │       └── create_github_issue_step.py
│   └── mappers/
│       ├── slack_payload_mapper.py    # Slack Block Kit 빌더 (workflow_id 포함)
│       └── github_issue_mapper.py     # issue draft → GitHub API payload
│
└── infrastructure/                    # 인프라 구현체
    ├── queue/
    │   └── sqs_publisher.py           # SqsQueueSender
    └── storage/
        ├── dynamodb/
        │   ├── workflow_instance_store.py   # IWorkflowInstanceRepository + DynamoDB 구현
        │   └── pending_action_store.py      # IIdempotencyRepository + DynamoDB 구현
        └── memory/
            ├── workflow_instance_store.py   # MemoryWorkflowInstanceStore (로컬/테스트)
            └── pending_action_store.py      # MemoryPendingActionStore (로컬/테스트)
```

---

## 실행 흐름

### 1. Ack Lambda (Lambda Function URL)

```
HTTP POST → lambda_ack.handler()
  └─ asyncio.run(_dispatch(event))
       └─ Bolt AsyncBoltRequest 생성
       └─ _app.async_dispatch(bolt_req)
            ├─ /feat, /refactor, /fix    → modal 오픈 (views_open)
            ├─ feat_submit 등             → IQueueSender.send(pipeline_start)
            ├─ issue_accept              → IQueueSender.send(accept, workflow_id)
            ├─ issue_reject              → modal 오픈 (workflow_id 포함)
            ├─ reject_submit             → IQueueSender.send(reject, workflow_id)
            ├─ issue_drop                → IWorkflowInstanceRepository.get(workflow_id) → drop modal 오픈
            └─ drop_submit               → IQueueSender.send(drop_restart, workflow_id)
       └─ statusCode + body + headers 반환 (3초 이내)
```

### 2. Worker Lambda (SQS Trigger)

```
SQS Records → lambda_worker.handler() → step_worker_handler.handler()
  └─ asyncio.run(_run())
       └─ for record in Records: _process(record.body)
            ├─ IIdempotencyRepository.try_acquire(dedup_id)   # 중복 방지
            ├─ GitHubMCPFactory.connect()
            ├─ WorkflowRuntime(repo, slack_client)
            │    ├─ pipeline_start → runtime.start(workflow_type, channel, user, message)
            │    │    └─ _execute_until_wait()
            │    │         ├─ FindRelevantBcStep           → bc_candidates
            │    │         ├─ GenerateIssueDraftStep       → issue_draft
            │    │         ├─ WaitIssueDraftConfirmationStep → Slack 전송 + WAITING
            │    │         └─ (사용자 응답 대기)
            │    │
            │    ├─ accept → runtime.resume(workflow_id, "accept")
            │    │    └─ _execute_until_wait()
            │    │         ├─ CreateGithubIssueStep        → github_issue_url
            │    │         └─ Slack chat_update (✅ 완료)
            │    │
            │    ├─ reject → runtime.resume(workflow_id, "reject", feedback)
            │    │    └─ _execute_until_wait()
            │    │         ├─ RegenerateIssueDraftStep     → issue_draft
            │    │         └─ WaitIssueDraftConfirmationStep → 새 Slack 메시지 + WAITING
            │    │
            │    └─ drop_restart → runtime.resume(workflow_id, "drop_restart", dropped_ids)
            │         └─ _execute_until_wait()
            │              ├─ RegenerateIssueDraftStep     → issue_draft (드롭 반영)
            │              └─ WaitIssueDraftConfirmationStep → 새 Slack 메시지 + WAITING
            └─ GitHubMCPFactory.disconnect()
```

### 3. 로컬 개발 서버

```
python -m src.local_server
  └─ AsyncSocketModeHandler (WebSocket)
       └─ 동일한 Bolt 핸들러 등록
       └─ LocalQueueSender → asyncio.create_task(step_worker_handler._process(body))
       └─ MemoryWorkflowInstanceStore, MemoryPendingActionStore
```

---

## 도메인 모델

### 이슈 템플릿 (`src/domain/issue/entities.py`)

```python
class Label(Enum):
    FEAT = "feat"
    REFACTOR = "refactor"
    FIX = "fix"

class BaseIssueTemplate(BaseModel):
    issue_title: str
    about: str

class FeatTemplate(BaseIssueTemplate):
    goal: str
    new_features: list[str]
    domain_rules: list[str]
    additional_info: str

class RefactorTemplate(BaseIssueTemplate):
    domain_rules: list[str]
    domain_constraints: list[str]
    goals: list[_Goal]            # as_is / to_be 쌍

class FixTemplate(BaseIssueTemplate):
    domain_rules: list[str]
    domain_constraints: list[str]
    implementation: list[_ImplementationStep]
    problems: list[_Problem]      # issue / suggestion 쌍
```

### WorkflowInstance (`src/workflow/models/workflow_instance.py`)

```
workflow_id          : UUID (불변 식별자, DynamoDB PK)
workflow_type        : "feat_issue" | "refactor_issue" | "fix_issue"
status               : WorkflowStatus (CREATED/RUNNING/WAITING/FAILED/COMPLETED)
current_step         : 현재 실행 중인 step 이름
state                : FeatIssueWorkflowState (step 간 공유 typed state)
pending_action_token : 사용자 응답 대기 토큰 (WAITING 상태, Slack 버튼 추적용)
slack_channel_id     : Slack 채널 ID
slack_user_id        : Slack 사용자 ID
slack_message_ts     : 현재 Slack 메시지 ts
created_at / ttl     : 생성 시각 / 만료 시각 (24시간)
```

DynamoDB 테이블: `barlow-workflow` (PK: `workflow_id`)

### FeatIssueWorkflowState (`src/workflow/models/workflow_state.py`)

```
user_message     : 원본 사용자 요청 (step 간 재사용)
bc_candidates    : RELEVANT_BC_FINDER 출력 JSON 문자열
bc_decision      : BC_DECISION_MAKER 출력 JSON 문자열 (미래 확장)
issue_draft      : 이슈 초안 JSON 문자열 (FeatTemplate 등)
github_issue_url : 생성된 GitHub 이슈 URL
user_feedback    : 사용자 재요청 시 입력
dropped_item_ids : 드롭된 항목 ID 목록 (e.g. "new_features::0")
```

---

## SQS 메시지 타입

| type | 발생 시점 | 주요 필드 |
|------|-----------|-----------|
| `pipeline_start` | 슬래시커맨드 Modal 제출 | subcommand, user_message, user_id, channel_id, dedup_id |
| `accept` | [수락] 버튼 클릭 | workflow_id, user_id, channel_id, dedup_id |
| `reject` | 재요청 Modal 제출 | workflow_id, user_id, channel_id, additional_requirements, dedup_id |
| `drop_restart` | 드롭 Modal 제출 | workflow_id, user_id, channel_id, dropped_ids[], dedup_id |

> `accept` / `reject` / `drop_restart` 는 Slack 버튼 `value` 필드에 `workflow_id` 를 담아 전달한다.

---

## AI 에이전트 파이프라인

### 에이전트 구성 (`src/agent/agent_info.py`)

| Agent | 입력 | 출력 | MCP |
|-------|------|------|-----|
| `RELEVANT_BC_FINDER` | user_message | `Candidates` (BC 후보 목록 + confidence) | readProjectTree |
| `FEAT_ISSUE_GEN` | bc_candidates | `FeatTemplate` | readProject |
| `REFACTOR_ISSUE_GEN` | bc_candidates | `RefactorTemplate` | readProject |
| `FIX_ISSUE_GEN` | bc_candidates | `FixTemplate` | readProject |
| `FEAT_REISSUE_GEN` | bc_candidates + issue_draft + feedback | `FeatTemplate` | readProject |
| `REFACTOR_REISSUE_GEN` | 동일 | `RefactorTemplate` | readProject |
| `FIX_REISSUE_GEN` | 동일 | `FixTemplate` | readProject |
| `BC_DECISION_MAKER` | user_message + bc_candidates | `BcDecision` | readProject |

### GitHub MCP 연결 (`src/agent/mcp.py`)

| MCP 서버 | 툴셋 | 용도 |
|---------|------|------|
| `readProjectTree` | GET_REPOSITORY_TREE, GET_FILE_CONTENTS | BC 후보 탐색 |
| `readProject` | GET_FILE_CONTENTS, SEARCH_CODE | 코드 분석 후 이슈 생성 |

---

## WorkflowRuntime 설계

### StepResult (`src/workflow/models/step_result.py`)

```python
class StepResult(BaseModel):
    status          : "success" | "waiting" | "failed"
    state_patch     : dict                              # WorkflowState에 반영할 데이터
    control_signal  : "continue" | "wait_for_user" | "stop"
    next_step       : str | None                        # 명시적 다음 step 지정
    user_action_request : dict | None                   # Slack 블록 payload
    internal_trace  : dict | None                       # token usage, raw output
```

### WorkflowStatus 전이

```
CREATED → RUNNING → WAITING ↔ RUNNING → COMPLETED
                           └→ FAILED
```

### Step 체인 (feat_issue 기준)

```
find_relevant_bc → generate_issue_draft → wait_issue_confirmation
                                                 │
                              ┌──────────────────┤
                           accept             reject / drop_restart
                              │                   │
                    create_github_issue   regenerate_issue_draft
                              │                   │
                           COMPLETED    wait_issue_confirmation (반복)
```

### Step 구현체

| Step | 위치 | state_patch 키 | control_signal |
|------|------|----------------|----------------|
| `FindRelevantBcStep` | steps/feat_issue/ | `bc_candidates` | continue |
| `GenerateIssueDraftStep` | steps/feat_issue/ | `issue_draft` | continue |
| `WaitIssueDraftConfirmationStep` | steps/common/ | (없음) | wait_for_user |
| `RegenerateIssueDraftStep` | steps/feat_issue/ | `issue_draft` | continue |
| `CreateGithubIssueStep` | steps/feat_issue/ | `github_issue_url` | stop |

### Resume 액션 → 다음 Step 매핑

| 사용자 액션 | 다음 step |
|------------|----------|
| `accept` | `create_github_issue` |
| `reject` | `regenerate_issue_draft` |
| `drop_restart` | `regenerate_issue_draft` |

---

## 저장소 구조

### infrastructure/storage/

| 클래스 | 환경 | 역할 |
|--------|------|------|
| `DynamoWorkflowInstanceStore` | 프로덕션 | WorkflowInstance CRUD |
| `DynamoPendingActionStore` | 프로덕션 | 중복 이벤트 차단 |
| `MemoryWorkflowInstanceStore` | 로컬/테스트 | WorkflowInstance 인메모리 |
| `MemoryPendingActionStore` | 로컬/테스트 | 인메모리 중복 방지 |

DynamoDB 테이블: `barlow-workflow` (PK: `workflow_id`)
Idempotency 테이블: `barlow-pending-action` (PK: `pk`, TTL 1시간)

### infrastructure/queue/

| 클래스 | 환경 | 역할 |
|--------|------|------|
| `SqsQueueSender` | 프로덕션 | SQS 메시지 전송 |

로컬 개발: `local_server.py` 내 `LocalQueueSender` (asyncio.create_task 직접 실행)

---

## 환경 변수 (`src/config.py`)

| 변수 | 필수 | 설명 |
|------|------|------|
| `SLACK_BOT_TOKEN` | Y | xoxb-... Slack Bot Token |
| `SLACK_SIGNING_SECRET` | Y | 요청 서명 검증 |
| `SLACK_APP_TOKEN` | 로컬만 | xapp-... Socket Mode용 |
| `GITHUB_TOKEN` | Y | GitHub PAT (MCP + REST API) |
| `OPENAI_API_KEY` | Y | OpenAI API 키 |
| `SQS_QUEUE_URL` | 프로덕션만 | Worker Lambda SQS URL |
| `TARGET_REPO` | Y | `owner/repo` 형식 GitHub 저장소 |

---

## 로컬 개발 도구 (`scripts/`)

```
scripts/
├── local_invoke.py        # CLI로 Agent 파이프라인 직접 호출 (실제 Agent 사용)
│                          # python scripts/local_invoke.py pipeline-start -s feat -m "..."
└── fixtures/              # 테스트용 JSON 페이로드
    ├── pipeline_start_feat.json
    ├── pipeline_start_refactor.json
    ├── pipeline_start_fix.json
    └── reject.json
```

Agent 출력은 `scripts/outputs/<timestamp>_<type>/` 에 자동 저장됨.
