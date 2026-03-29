# Barlow Automation — 아키텍처 설계 문서

---

## 전체 구조

```
Slack
  ↕  (api.slack.com 경유)
Ack Lambda (barlow-slack-ack)       ← Function URL, 3초 이내 응답
  │
  ├─ send ──▶ SQS (barlow-queue)
  │               │
  │           trigger
  │               │
  │               ▼
  └─ read/write ──▶ Worker Lambda (barlow-automation-worker)
  (cancel path)        │
                       ├─ read/write ──▶ DynamoDB
                       ├─ chat_postMessage / views.open ──▶ Slack
                       └─ create issue ──▶ GitHub
```

---

## 설계 철학

### 1. 왜 서버리스인가

월 30회 미만의 호출량에서 서버를 상시 운영하는 것은 낭비다.

| | 서버 (ECS Fargate) | 현재 (Lambda + SQS) |
|---|---|---|
| 비용 | ~$15/월 (상시) | ~$0 (호출당) |
| 운영 | 패치, 스케일링 직접 관리 | 관리 불필요 |
| 적합 규모 | 트래픽이 지속적일 때 | 트래픽이 희소할 때 |

현재 규모에서는 Lambda가 압도적으로 합리적이다.

---

### 2. SQS가 존재하는 이유

**Slack의 3초 응답 제한** 하나다.

Slack은 이벤트를 전송한 후 3초 안에 HTTP 200을 받지 못하면 timeout으로 처리하고 재전송한다. AI agent + GitHub MCP 호출은 수십 초 ~ 수 분이 걸린다.

Lambda는 `handler()`가 return하는 순간 실행 컨텍스트가 freeze된다. 서버처럼 백그라운드 태스크를 유지할 수 없다.

```
# 서버 — 가능
async def handle():
    asyncio.create_task(long_work())  # 프로세스가 살아있어 유지됨
    return Response(200)

# Lambda — 불가능
def handler(event, context):
    asyncio.create_task(long_work())  # return 후 freeze, 실행 안 됨
    return {"statusCode": 200}
```

따라서 긴 작업을 SQS로 위임하고 즉시 return하는 구조가 필연적이다.

```
Ack Lambda:  ack() → _put_sqs() → return  (3초 이내)
Worker Lambda: SQS 트리거 → AI agent 실행  (최대 900초)
```

---

### 3. Ack Lambda의 실제 역할 — Servlet

이름은 "Ack Lambda"지만 실제로는 **Slack 이벤트를 처리하는 Servlet**에 가깝다.

```
Slack HTTP 요청 → Function URL → Ack Lambda → HTTP 응답
```

Slack Bolt에서 `process_before_response=True`를 사용하므로
`ack()`를 먼저 호출해도 **실제 HTTP 응답은 handler가 return할 때** 전송된다.
따라서 handler 전체 실행 시간이 3초를 넘으면 Slack이 timeout한다.

역할 분리 기준:

| Ack Lambda (동기) | Worker Lambda (비동기) |
|---|---|
| 3초 이내 완결 가능한 것 | 3초 이내 완결 불가능한 것 |
| modal 열기, Slack ack | AI agent, GitHub API |
| cancel (DynamoDB + Slack) | 워크플로우 step 실행 |

`/drop`, `issue_drop`이 Ack Lambda에서 직접 처리되는 것은 SQS 왕복 없이 3초 안에 충분히 끝나기 때문이다.

---

### 4. Producer-Consumer — 완전한 분리가 불가능한 이유

SQS 관점에서는 명확한 Producer-Consumer 구조다.

```
Producer          Broker    Consumer
Ack Lambda  ──▶  SQS  ──▶  Worker Lambda
```

순수 Producer는 입력을 받아 큐에 넣고 끝낸다. 호출자에게 돌려주는 출력이 없다.

```
순수 Producer:  Slack 이벤트 수신 → SQS.send() → return
                                                    ↑ Slack에 아무것도 반환 안 함
```

그러나 Ack Lambda는 Slack에 두 가지를 반드시 돌려줘야 한다.

**1. HTTP 200 ack** — Slack이 이벤트를 보낸 후 3초 안에 받지 못하면 timeout으로 처리하고 재전송한다.

**2. `views_open`** — Slack이 `/feat` 커맨드와 함께 발급하는 `trigger_id`는 3초 후 만료된다. modal을 열려면 이 토큰이 유효한 시점, 즉 Ack Lambda 안에서 즉시 호출해야 한다. SQS → Worker로 넘기면 도착 시점에 이미 만료되어 modal을 열 수 없다.

```python
@app.command("/feat")
async def handle_feat(ack, client, command):
    await ack()                             # 출력 1: HTTP 200
    await client.views_open(
        trigger_id=command["trigger_id"],   # 출력 2: modal 열기 (3초 내 필수)
        ...
    )
    _put_sqs({...})                         # 긴 작업만 SQS로 위임
```

```
현재 Ack Lambda:  Slack 이벤트 수신 → HTTP 200   (Slack으로)
                                    → views_open  (Slack으로)
                                    → SQS.send()  (Worker로)
```

두 가지 출력이 존재하므로 순수 Producer가 될 수 없다. Ack Lambda는 Slack 이벤트를 받아 처리하는 **Controller** 역할을 유지하면서, 오래 걸리는 작업만 SQS로 위임하는 구조가 구조적으로 최선이다.

---

### 5. 상태 관리 — DynamoDB

Lambda는 stateless다. 여러 번의 Lambda 실행에 걸쳐 진행되는 워크플로우 상태를 DynamoDB에 저장한다.

```
Worker #1 실행 → 상태 저장 → Lambda 종료
Worker #2 실행 → 상태 로드 → 이어서 실행
```

DynamoDB의 역할은 **step 라우팅이 아닌 누적 컨텍스트 보존**이다.
다음 step을 결정하는 것은 SQS 메시지의 `event_type`과 `RESUME_MAP`이다.

```python
RESUME_MAP = {
    "accept":           "create_github_issue",
    "extend_existing":  "generate_issue_draft",
    ...
}
# SQS 메시지 action → RESUME_MAP → 다음 step 결정
# DynamoDB → 이전 step 결과 (BC 목록, 이슈 목록, 초안) 로드
```

---

### 6. Dedup — cold start에서 시작되는 인과관계

```
Lambda cold start (최대 2~3초)
    → handler 전체 실행 시간 3초 초과
    → Slack timeout
    → Slack이 동일 이벤트 재전송
    → SQS에 중복 메시지 전송
    → Worker Lambda 중복 실행
    → 같은 워크플로우 두 번 처리
```

이를 막기 위해 두 가지 dedup이 존재한다.

**pending-action** (`barlow-pending-action`):
- Slack `action_ts` / `view_id` 기반, TTL 1h
- Worker 처리 직전 `attribute_not_exists(pk)` 조건부 PutItem
- Slack retry, SQS at-least-once, 버튼 중복 클릭 모두 차단

**active-session** (`barlow-active-session`):
- `{channel_id}#{user_id}` 키, TTL 24h
- 동일 사용자가 같은 채널에서 워크플로우를 중복 시작하지 못하게 차단

---

### 7. 서버리스 임피던스 미스매치

Slack 봇의 상호작용 모델은 본질적으로 **상태 있는 장기 세션**이다.

```
/feat 입력 → modal → AI 분석 → 결정 모달 → 초안 확인 → 이슈 생성
(수 분에 걸친 대화)
```

서버라면 자연스럽게 처리되는 것들이 서버리스에서는 직접 구현해야 한다.

| 서버의 자연스러운 것 | 서버리스에서 대체한 것 |
|---|---|
| 메모리 상태 | DynamoDB |
| 백그라운드 스레드 | SQS + Worker Lambda |
| 세션/컨텍스트 유지 | GRAPH + RESUME_MAP + `_execute_until_wait()` |
| 장기 대기 (사람 승인) | WAIT 상태 + Lambda 종료 + 재트리거 |

현재 코드의 복잡도 대부분은 이 **임피던스 미스매치를 해소하기 위한 비용**이다.

---

### 8. Step Functions를 쓰지 않는 이유

Step Functions는 이 임피던스 미스매치를 네이티브로 해결하는 서비스다.

```
GRAPH + RESUME_MAP  →  Step Functions State Machine
DynamoDB 상태 저장  →  Step Functions 내장
WAIT 패턴          →  waitForTaskToken 네이티브 지원
```

그러나 현재 규모에서는 도입하지 않는다.

| | 현재 (SQS + DynamoDB) | Step Functions |
|---|---|---|
| 개발 속도 | 빠름 | ASL 정의 별도 필요 |
| 비용 | ~$0 | 상태 전이당 과금 |
| 복잡도 | 낮음 | 높음 |
| 워크플로우 가시성 | CloudWatch 로그 | 콘솔에서 시각화 |

월 30회 호출에서 Step Functions 도입은 오버엔지니어링이다.
step 수가 급증하거나 워크플로우가 복잡해질 때 재검토한다.

---

## 컴포넌트 요약

| 컴포넌트 | 역할 | 제약 |
|---|---|---|
| Ack Lambda | Slack 이벤트 수신, 동기 처리, SQS 위임 | 29초 timeout, 3초 ack |
| SQS | Ack↔Worker 생명주기 분리, 재시도 버퍼 | visibility timeout = 900s |
| Worker Lambda | 워크플로우 step 실행 (AI agent, GitHub) | 900초 timeout |
| DynamoDB | 워크플로우 상태 및 dedup 저장 | 3개 테이블, TTL 관리 |
| GitHub API | 이슈 생성, 관계 설정 | REST API 직접 호출 |

---

## 개선 검토 시점

| 상황 | 검토할 것 |
|---|---|
| cold start가 반복적으로 문제가 될 때 | Provisioned Concurrency |
| step 수가 10개 이상으로 늘어날 때 | Step Functions 전환 |
| 트래픽이 지속적으로 증가할 때 | ECS Fargate 전환 |
| pending-action 관리가 복잡해질 때 | FIFO Queue로 전환 |
