# Socket Mode → Lambda + DynamoDB 마이그레이션 계획

---

## 인프라 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  외부                                                                        │
│                                                                              │
│   ┌──────────┐          ┌───────────────────┐      ┌──────────────────────┐ │
│   │  Slack   │          │  GitHub Copilot   │      │     OpenAI API       │ │
│   │  (User)  │          │  MCP Server       │      │  (gpt-4o-mini)       │ │
│   └────┬─────┘          │  api.githubcopilot│      └──────────┬───────────┘ │
│        │                │  .com/mcp/        │                 │             │
└────────┼────────────────└────────┬──────────┘─────────────────┼─────────────┘
         │                         │                             │
         │ HTTPS POST              │ MCP (Streamable HTTP)       │ HTTPS
         │ Events API              │                             │
         ▼                         │                             │
┌────────────────────────────────────────────────────────────────────────────┐
│  AWS                                                                        │
│                                                                             │
│  ┌──────────────────────┐                                                   │
│  │  Lambda Function URL │                                                   │
│  │  (또는 API Gateway)  │                                                   │
│  └──────────┬───────────┘                                                   │
│             │                                                                │
│             ▼                                                                │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │  Ack Lambda                                              │               │
│  │                                                          │               │
│  │  1. Slack Signature 검증                                 │               │
│  │  2. event_type 판별                                      │               │
│  │     ├─ pipeline_start → SQS 큐잉                        │               │
│  │     ├─ reject_modal   → SQS 큐잉 (msg_ts 포함)          │               │
│  │     ├─ drop_restart   → SQS 큐잉 (msg_ts 포함)          │               │
│  │     └─ issue_accept   → pending 삭제                    │               │
│  │  3. HTTP 200 ack (3초 이내)                              │               │
│  │  4. (Modal trigger_id 필요한 views_open은 여기서 직접)   │               │
│  └──────────────────────────┬───────────────────────────────┘               │
│                             │                                                │
│             ┌───────────────┘                                                │
│             │ SendMessage                                                    │
│             ▼                                                                │
│  ┌──────────────────────┐        ┌───────────────────────────────────────┐  │
│  │  SQS Queue           │        │  DynamoDB                             │  │
│  │  barlow-work-queue   │        │                                       │  │
│  │                      │        │  ┌─────────────────────────────────┐  │  │
│  │  - pipeline_start    │        │  │  barlow-sessions                │  │  │
│  │  - reject_modal      │        │  │  pk: "channel:user"             │  │  │
│  │  - drop_restart      │        │  │  status: RUNNING | IDLE         │  │  │
│  │                      │        │  │  ttl: Unix timestamp            │  │  │
│  │  DLQ ──────────────► │        │  └─────────────────────────────────┘  │  │
│  │  barlow-work-dlq     │        │                                       │  │
│  └──────────┬───────────┘        │  ┌─────────────────────────────────┐  │  │
│             │ trigger             │  │  barlow-pending                 │  │  │
│             ▼                    │  │  pk: "channel:user"             │  │  │
│  ┌──────────────────────────────────┐  subcommand, user_message       │  │  │
│  │  Worker Lambda         │      │  │  inspector_output               │  │  │
│  │  (timeout: 15분)       │      │  │  typed_output (JSON)            │  │  │
│  │                        │      │  │  typed_output_type              │  │  │
│  │  [pipeline_start]      │      │  │  ttl: Unix timestamp            │  │  │
│  │   Inspector Agent ─────┼──────┼──► get_repository_tree            │  │  │
│  │      ↓                 │      │  └─────────────────────────────────┘  │  │
│  │   Issue Gen Agent ─────┼──────┼──► get_file_contents, search_code    │  │  │
│  │      ↓                 │      │                                       │  │  │
│  │   barlow-pending 저장  ◄──────┤                                       │  │  │
│  │                        │      └───────────────────────────────────────┘  │  │
│  │  [reject_modal]        │                                                  │  │
│  │   barlow-pending 조회 ◄┘                                                  │  │
│  │      ↓ without()       │                                                  │  │
│  │   Reissue Agent ───────┼───────────────────────────────────────────────► │  │
│  │      ↓                 │                                                  │  │
│  │   barlow-pending 갱신  │                                                  │  │
│  │                        │                                                  │  │
│  │  [drop_restart]        │                                                  │  │
│  │   barlow-pending 조회  │                                                  │  │
│  │      ↓ user_message    │                                                  │  │
│  │   Inspector부터 재실행  │                                                  │  │
│  │                        │                                                  │  │
│  │  결과: chat.postMessage│                                                  │  │
│  └───────────┬────────────┘                                                  │  │
│              │ HTTPS                                                         │  │
└──────────────┼───────────────────────────────────────────────────────────────┘  │
               │                                                                   │
               ▼                                                                   │
         ┌──────────┐                                                              │
         │  Slack   │◄─────────────────────────────────────────────────────────── ┘
         │  API     │  chat.postMessage / views_open
         └──────────┘
```

### 컴포넌트 요약

| 컴포넌트 | 역할 | 비고 |
|----------|------|------|
| Lambda Function URL | Slack 이벤트 수신 엔드포인트 | API Gateway 대체 가능 |
| Ack Lambda | 즉시 ack + SQS 큐잉 | 경량, 빠른 응답 전용 |
| SQS Queue | Ack-Worker 간 비동기 디커플링 | DLQ로 실패 메시지 보존 |
| Worker Lambda | 실제 파이프라인 실행 | timeout 15분, MCP connect/disconnect 포함 |
| DynamoDB `barlow-idempotency` | LLM 중복 호출 방지 | pk: Slack `message_ts`, TTL 1시간 |
| DynamoDB `barlow-pending` | 이슈 컨텍스트 영속 저장 | pk: Slack `message_ts`, TTL 24시간 |
| GitHub MCP Server | 코드베이스 탐색 도구 제공 | Worker Lambda 내 per-invocation connect |
| OpenAI API | Agent LLM 실행 | Worker Lambda에서 직접 호출 |

---

## 현재 아키텍처 vs 목표 아키텍처

| 항목 | 현재 (Socket Mode) | 목표 (Lambda) |
|------|-------------------|---------------|
| 연결 방식 | WebSocket (상시 연결) | HTTP (Events API + Lambda URL) |
| 실행 환경 | 단일 프로세스, always-on | 이벤트 드리븐, 요청별 cold start |
| 중복 호출 방지 | `InMemorySessionManager` (channel:user 락) | DynamoDB idempotency (Slack `ts` 기반) |
| 이슈 컨텍스트 (`_pending`) | 프로세스 내 dict | DynamoDB |
| GitHub MCP | 앱 시작 시 1회 연결, 종료 시 해제 | 요청마다 connect/disconnect |
| 장기 실행 파이프라인 | asyncio 내 자연스럽게 처리 | **핵심 난제** — Slack 3초 ack + 파이프라인 수분 소요 |

---

## 핵심 설계 결정

### 1. Slack 3초 ack 문제 해결 — 이중 Lambda 패턴

Slack은 이벤트 수신 후 3초 내 HTTP 200을 요구한다.
Inspector + Issue Gen 파이프라인은 수분이 걸릴 수 있으므로 Lambda를 두 계층으로 분리한다.

```
Slack
  │  HTTP POST (slash command / view submit / action)
  ▼
[Ack Lambda]  ← Lambda Function URL or API Gateway
  │  즉시 HTTP 200 ack
  │  SQS로 작업 큐잉 (payload: subcommand, user_message, channel, user)
  ▼
[SQS Queue]
  │  trigger
  ▼
[Worker Lambda]  ← 실제 파이프라인 실행
  │  Inspector → Issue Gen (수분 소요 가능, Lambda timeout 15분)
  ▼
Slack API (chat.postMessage)
```

- **Ack Lambda**: 경량, 빠른 응답 전용. 세션 획득 + SQS 큐잉만 수행.
- **Worker Lambda**: 파이프라인 실행 전용. timeout 15분으로 설정.

### 2. Modal submit / action 버튼 처리

Modal submit(`view_submission`)과 버튼 액션(`block_actions`)도 동일하게 Ack Lambda에서 즉시 ack 후 SQS로 위임.

```
Modal submit → Ack Lambda (ack) → SQS (type: "view_submit", payload)
버튼 클릭   → Ack Lambda (ack) → SQS (type: "action", payload)
```

### 3. GitHub MCP 서버 수명 주기

현재는 앱 시작/종료 시 1회 connect/disconnect지만, Lambda는 stateless이므로 Worker Lambda 내에서 매 호출마다 connect → 실행 → disconnect.

```python
async with mcp_server:
    result = await agent.run(message)
```

Lambda 컨테이너 재사용(warm start)을 기대한 전역 연결은 비결정적이므로 사용하지 않는다.

---

## Idempotency 설계 (세션 방식 대체)

### 세션 방식의 문제

기존 `channel:user` 락 방식은 "사용자가 처리 중인지"를 추적했다. 이는 두 가지 문제가 있다:

1. **Slack 재시도 미대응**: Slack은 5xx 응답 시 동일 이벤트를 최대 3회 재전송한다. 세션 락은 사용자 단위 직렬화이므로 동일 이벤트의 중복 처리를 막지 못한다.
2. **사용자 단위 직렬화의 불필요한 제약**: 사용자가 서로 다른 두 이슈를 동시에 다루는 것을 원천 차단한다.

### Slack `ts` 기반 Idempotency

Slack의 모든 메시지는 고유한 `ts` (타임스탬프 문자열)를 가진다. 버튼이 포함된 이슈 결과 메시지의 `ts`를 idempotency 키로 사용한다.

- `body["message"]["ts"]` — 버튼 액션 발생 시 해당 메시지의 ts
- `body["container"]["message_ts"]` — view submission 시 원본 메시지의 ts

Worker Lambda가 시작할 때 DynamoDB에 조건부 쓰기를 시도한다. 이미 존재하면 (Slack 재시도 또는 중복 클릭) 즉시 종료한다.

```
PutItem(
  pk = message_ts,
  status = "PROCESSING",
  ttl = now + 3600,
  ConditionExpression = "attribute_not_exists(pk)"
)
```
→ 실패(ConditionalCheckFailedException): 이미 처리 중 또는 완료 → Worker 즉시 종료.

### DynamoDB 테이블 설계

#### Table 1: `barlow-idempotency`

| 필드 | 타입 | 설명 |
|------|------|------|
| `pk` (PK) | String | Slack `message_ts` (이슈 결과 메시지의 ts) |
| `status` | String | `PROCESSING` \| `DONE` |
| `ttl` | Number | Unix timestamp (1시간 — 처리 완료 후 자동 만료) |

#### Table 2: `barlow-pending`

pk를 `channel:user`에서 **Slack `message_ts`** 로 변경한다. 각 이슈 결과 메시지가 자신의 컨텍스트를 독립적으로 소유한다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `pk` (PK) | String | Slack `message_ts` (이슈 결과 메시지의 ts) |
| `subcommand` | String | `feat` \| `refactor` \| `fix` |
| `user_message` | String | Modal to_prompt() 결과 |
| `inspector_output` | String | Inspector Agent JSON 출력 |
| `typed_output` | String | FeatTemplate 등 JSON 직렬화 (`model.model_dump_json()`) |
| `typed_output_type` | String | `feat` \| `refactor` \| `fix` (역직렬화용) |
| `ttl` | Number | Unix timestamp (24시간) |

`typed_output` 역직렬화:
```python
template_cls = {"feat": FeatTemplate, "refactor": RefactorTemplate, "fix": FixTemplate}
typed_output = template_cls[item["typed_output_type"]].model_validate_json(item["typed_output"])
```

### `message_ts` 흐름

```
[pipeline_start]
  Worker Lambda 완료
    → chat.postMessage 호출
    → 응답의 ts (= 이슈 결과 메시지 ts)
    → barlow-pending에 pk로 저장
    → barlow-idempotency 상태를 DONE으로 갱신

[reject_modal / drop_restart]
  SQS 메시지에 원본 message_ts 포함
    → barlow-pending 조회 (pk = message_ts)
    → 처리 완료 후 새 chat.postMessage 응답 ts를 새 pk로 저장
    → 기존 pk 항목 삭제
```

---

## SQS 메시지 스키마

event_type별로 Worker Lambda가 수행할 작업이 다르므로 페이로드를 분리한다.

### `pipeline_start` — 신규 파이프라인 (슬래시 커맨드 Modal 제출)
```json
{
  "event_type": "pipeline_start",
  "subcommand": "feat",
  "user": "U12345",
  "channel": "C12345",
  "user_message": "[feat] ..."
}
```
Worker 동작: Inspector → Issue Gen → `barlow-pending` 저장 → Slack 전송

---

### `reject_modal` — 재요청 (재요청 Modal 제출)
```json
{
  "event_type": "reject_modal",
  "user": "U12345",
  "channel": "C12345",
  "message_ts": "1234567890.123456",
  "dropped_ids": ["new_features::0", "domain_rules::1"],
  "additional_request": "인증 관련 항목을 더 강조해주세요"
}
```
Worker 동작:
1. `barlow-idempotency` 조건부 쓰기 (`pk = message_ts`) → 실패 시 즉시 종료
2. `barlow-pending`에서 `pk = message_ts` 로 컨텍스트 조회
3. `typed_output.without(dropped_ids)` — 코드 레벨 필터링
4. Reissue Agent 실행 (`[Inspector Context] + [Current Issue Draft] + Additional requirements`)
5. 새 결과 메시지 전송 → 응답 `ts` 획득
6. `barlow-pending` 신규 pk(새 `ts`)로 저장, 기존 pk 삭제

> `subcommand`와 `user_message`는 SQS에 포함하지 않고 `barlow-pending`에서 조회한다.

---

### `drop_restart` — 드롭 후 재탐색 (드롭 버튼 클릭)
```json
{
  "event_type": "drop_restart",
  "user": "U12345",
  "channel": "C12345",
  "message_ts": "1234567890.123456"
}
```
Worker 동작:
1. `barlow-idempotency` 조건부 쓰기 → 실패 시 즉시 종료
2. `barlow-pending`에서 `pk = message_ts` 로 `user_message`, `subcommand` 조회
3. `barlow-pending` 기존 항목 삭제 (컨텍스트 폐기)
4. Inspector부터 전체 파이프라인 재실행 (`pipeline_start`와 동일 흐름)

---

### `barlow-pending` 역할 요약

| 사용 시점 | pk | 읽는 필드 | 쓰는 필드 |
|----------|----|----------|----------|
| Issue Gen 완료 후 | 결과 메시지 `ts` | — | 전체 저장 |
| `reject_modal` Worker | 원본 메시지 `ts` | `inspector_output`, `typed_output`, `subcommand` | 새 `ts`로 신규 저장, 기존 삭제 |
| `drop_restart` Worker | 원본 메시지 `ts` | `user_message`, `subcommand` | 삭제 후 재파이프라인 결과로 재저장 |
| 수락 버튼 | 원본 메시지 `ts` | — | 항목 삭제 |

---

## 파일 구조 변경

### 현재 구조 → 목표 구조

```
src/                                       src/
├── config.py                              ├── config.py                    # 변경 없음
├── logging_config.py                      ├── logging_config.py            # 변경 없음
├── main.py              ────────────────► ├── lambda_ack.py                # NEW: Ack Lambda 진입점
│                                          ├── lambda_worker.py             # NEW: Worker Lambda 진입점
│
├── slack/                                 ├── slack/
│   ├── app.py           ────────────────► │   ├── app.py                   # CHANGE: Socket→HTTP 핸들러
│   ├── event_router.py                    │   ├── event_router.py          # 변경 없음
│   └── handlers/                          │   └── handlers/
│       ├── slash_handler.py  ───────────► │       ├── slash_handler.py     # CHANGE: 경량화 (ack + 큐잉만)
│       ├── slash_modal_templates.py       │       ├── slash_modal_templates.py  # 변경 없음
│       ├── mention_handler.py             │       ├── mention_handler.py   # 변경 없음
│       ├── message_handler.py             │       ├── message_handler.py   # 변경 없음
│       └── _reply.py                      │       └── _reply.py            # 변경 없음
│
├── session/             ────────────────► │                                 # REMOVE: session/ 패키지 제거
│   ├── manager.py                         │                                 # (idempotency로 대체)
│   └── models.py                          │
│
│                                          ├── store/                       # NEW: 영속 상태 저장소
│                                          │   ├── idempotency.py           # NEW: barlow-idempotency CRUD
│                                          │   ├── pending.py               # NEW: barlow-pending CRUD
│                                          │   └── models.py                # NEW: PendingContext (현 _IssueContext)
│
│                                          ├── queue/                       # NEW: SQS 메시지 발행
│                                          │   ├── producer.py              # NEW: SQS SendMessage
│                                          │   └── models.py                # NEW: SQS 페이로드 스키마
│
│                                          ├── pipeline/                    # NEW: 파이프라인 실행 (Worker 전용)
│                                          │   └── executor.py              # NEW: pipeline_start/reject/drop 실행
│
└── agent/                                 └── agent/                       # 변경 없음
    ├── base.py                                ├── base.py
    ├── usage.py                               ├── usage.py
    ├── agents/                                ├── agents/
    └── runner/                                └── runner/
```

### 파일별 변경 이유

| 파일 | 변경 | 이유 |
|------|------|------|
| `main.py` | 제거 | Socket Mode 루프 불필요. Lambda 진입점으로 대체 |
| `lambda_ack.py` | 신규 | Ack Lambda 핸들러 (`def handler(event, context)`) |
| `lambda_worker.py` | 신규 | Worker Lambda 핸들러. SQS 이벤트를 받아 pipeline 실행 |
| `slack/app.py` | 수정 | `AsyncSocketModeHandler` → `AsyncSlackRequestHandler` |
| `slack/handlers/slash_handler.py` | 수정 | 파이프라인 실행 코드 제거, SQS 큐잉 + ack만 남김. `_pending` dict 제거 |
| `session/` | **제거** | idempotency 방식으로 대체. `ISessionManager` 및 구현체 전부 삭제 |
| `store/idempotency.py` | 신규 | `barlow-idempotency` 조건부 쓰기 / DONE 갱신 |
| `store/models.py` | 신규 | `PendingContext` dataclass (현 `_IssueContext`를 DynamoDB 저장 가능 형태로 분리) |
| `store/pending.py` | 신규 | `barlow-pending` 테이블 CRUD (`save`, `get`, `save_new_and_delete_old`, `delete`) |
| `queue/models.py` | 신규 | SQS 메시지 Pydantic 스키마 (`PipelineStartEvent`, `RejectModalEvent`, `DropRestartEvent`) |
| `queue/producer.py` | 신규 | `boto3` SQS `send_message` 래퍼 |
| `pipeline/executor.py` | 신규 | `_execute_pipeline` / `handle_reject_modal` / `handle_drop` 로직 이동. Worker Lambda에서만 사용 |

### 책임 재분배

```
현재 slash_handler.py                      마이그레이션 후
─────────────────────────────              ─────────────────────────────────────
_pending dict                  ────────►  store/pending.py (DynamoDB)
_IssueContext                  ────────►  store/models.py (PendingContext)
_execute_pipeline()            ────────►  pipeline/executor.py
_run_issue_pipeline()          ────────►  pipeline/executor.py
handle_feat/refactor/fix       ────────►  slash_handler.py (ack + views_open + SQS)
handle_reject_modal()          ────────►  slash_handler.py (ack + SQS)
                                           pipeline/executor.py (실제 reissue 실행)
handle_drop()                  ────────►  slash_handler.py (ack + SQS)
                                           pipeline/executor.py (실제 재탐색 실행)
```

---

## SQS vs Step Functions

### 이 시스템의 파이프라인 구조

```
pipeline_start:  Inspector Agent → Issue Gen Agent → Slack 전송
reject_modal:    (DynamoDB 조회) → Reissue Agent  → Slack 전송
drop_restart:    Inspector Agent → Issue Gen Agent → Slack 전송
```

2단계 순차 실행, 분기 없음, 병렬 없음.

### 비교

| 항목 | SQS + Worker Lambda | Step Functions |
|------|--------------------|--------------------|
| 구조 | 단일 Worker Lambda가 처음부터 끝까지 실행 | 각 단계를 별도 Lambda로 분리, 상태 머신이 조율 |
| 적합한 경우 | 단순 순차 실행, 하나의 작업 단위 | 복잡한 분기, 병렬, 재시도, 대기 상태 |
| 실패 처리 | DLQ로 메시지 보존, 수동 재처리 | 단계별 재시도 정책, 실패 단계 특정 가능 |
| 가시성 | CloudWatch 로그만 | 콘솔에서 단계별 실행 상태 시각화 |
| 비용 | SQS 요청당 과금 (매우 저렴) | 상태 전환당 과금 (Standard) / 실행 시간당 (Express) |
| 코드 복잡도 | Worker Lambda 1개, 단순 | Lambda 여러 개 + 상태 머신 정의(JSON/YAML) |
| timeout 관리 | Worker Lambda 단일 15분 제한 | 단계별 Lambda timeout 분산 가능 |

### 현재 SQS로 충분한 이유

Inspector와 Issue Gen은 별도로 분리할 이유가 없고, 중간 결과(`inspector_output`)는 어차피 `barlow-pending`에 저장하므로 Step Functions의 단계 간 상태 전달 이점도 없다.

### Step Functions로 전환을 고려해야 하는 시점

| 조건 | 설명 |
|------|------|
| Inspector 단독 15분 초과 가능성 | 대형 레포 분석 시 단일 Lambda timeout 초과 위험 |
| 단계별 자동 재시도 필요 | Inspector 실패 시 Issue Gen skip + Inspector만 재실행 |
| 병렬 실행 필요 | Inspector 결과를 feat/refactor/fix에 동시에 전달 |
| 실패 원인 단계 추적 필요 | CloudWatch 로그만으로 디버깅이 어려워지는 시점 |

---

## 변경이 필요한 컴포넌트

### 1. `src/slack/app.py`
- `AsyncSocketModeHandler` → `AsyncSlackRequestHandler` (HTTP 핸들러)
- Slack Bolt의 `slack_bolt.adapter.aws_lambda` 사용

### 2. `src/main.py`
- `handler.start_async()` 루프 제거
- Lambda 핸들러 함수로 교체 (`def handler(event, context)`)
- GitHub MCP `connect/disconnect`를 Worker Lambda 내부로 이동

### 3. `src/session/manager.py`
- `InMemorySessionManager` → `DynamoDbSessionManager` 구현
- `ISessionManager` 인터페이스 유지 (변경 없음)

```python
class DynamoDbSessionManager(ISessionManager):
    async def try_acquire(self, key: str) -> bool:
        try:
            table.put_item(
                Item={"pk": key, "status": "RUNNING", "ttl": now + 1800},
                ConditionExpression="attribute_not_exists(pk) OR #s = :idle",
            )
            return True
        except ConditionalCheckFailedException:
            return False

    async def release(self, key: str) -> None:
        table.update_item(Key={"pk": key}, UpdateExpression="SET #s = :idle")
```

### 4. `src/slack/handlers/slash_handler.py`
- `_pending` dict → DynamoDB `barlow-pending` 테이블 읽기/쓰기
- `_run_issue_pipeline` → SQS 큐잉으로 교체 (Ack Lambda)
- 실제 파이프라인 실행 → Worker Lambda로 분리

### 5. `src/agent/agents/github.py`
- `GitHubMCPFactory.connect/disconnect` → 앱 수준 생명 주기 제거
- Worker Lambda 실행 시 컨텍스트 매니저 방식으로 전환

---

## 단계별 마이그레이션 순서

### Phase 1 — 상태 외부화 (인프라 준비)
1. DynamoDB 테이블 2개 생성 (`barlow-sessions`, `barlow-pending`)
2. `DynamoDbSessionManager` 구현 및 단위 테스트
3. `_pending` dict → DynamoDB CRUD 헬퍼 작성
4. 로컬에서 `InMemory` → `DynamoDB` 교체 후 기존 소켓 모드로 동작 검증

### Phase 2 — 비동기 파이프라인 분리
1. SQS 큐 생성
2. Worker Lambda 함수 작성 (파이프라인 실행 로직만 추출)
3. Worker Lambda에서 MCP connect/disconnect를 함수 내부로 이동
4. 소켓 모드 앱에서 파이프라인 호출을 SQS 큐잉으로 교체 후 검증

### Phase 3 — HTTP 모드 전환
1. Slack App 설정에서 Events API URL 등록 (Lambda Function URL)
2. `AsyncSocketModeHandler` → `AsyncSlackRequestHandler` 교체
3. Ack Lambda 작성 (ack + SQS 큐잉)
4. `main.py`를 Lambda 핸들러로 교체
5. 소켓 모드 완전 제거

### Phase 4 — 운영 안정화
1. Worker Lambda timeout 조정 (최대 15분)
2. SQS Dead Letter Queue 설정 (파이프라인 실패 처리)
3. DynamoDB TTL 활성화로 스테일 세션/컨텍스트 자동 정리
4. CloudWatch 알람 설정

---

## 주의사항

| 항목 | 내용 |
|------|------|
| Slack signing secret 검증 | HTTP 모드에서는 반드시 `X-Slack-Signature` 검증 필요 (Bolt가 자동 처리) |
| Modal trigger_id 유효시간 | 3초 제한 — Ack Lambda에서 즉시 `views_open` 호출해야 함 (SQS 위임 불가) |
| Worker Lambda 동시성 | 동일 사용자의 중복 Worker 실행 방지는 DynamoDB 세션 락으로 보장 |
| MCP 연결 지연 | 매 Worker 호출마다 MCP connect 추가 지연 발생 (수백ms) |
| typed_output 직렬화 | `model_dump_json()` / `model_validate_json()` 으로 DynamoDB 저장/복원 |
