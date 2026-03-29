# Barlow Automation — 포트폴리오

- **기간**: 2025 개인 프로젝트
- **역할**: 설계 · 구현 전담
- **기술 스택**: Python 3.12, AWS Lambda · SQS · DynamoDB, Slack Bolt, Claude API, OpenAI Agents SDK, GitHub MCP

---

## 무엇을 만들었나

개발팀 내부 도구. Slack 슬래시 커맨드 하나로 GitHub 이슈를 자동 생성한다.

```
개발자: /feat "결제 모듈에 환불 기능 추가해줘"

시스템: GitHub 코드베이스 분석
      → 관련 Bounded Context 탐색
      → 기존 이슈 중복 확인 및 관계 판단
      → 이슈 초안 생성 (제목, 본문, 레이블)
      → 개발자 확인 후 GitHub 이슈 자동 생성
```

---

## 풀어야 했던 문제들

### 문제 1. AI 응답이 느린데 Slack은 3초 안에 응답을 요구한다

Slack은 이벤트를 전송하고 3초 안에 HTTP 200을 받지 못하면 timeout → 재전송한다.
AI agent + GitHub MCP 실행은 수십 초에서 수 분이 걸린다.

Lambda는 `handler()` return 시 실행 컨텍스트가 freeze된다. 서버처럼 백그라운드 태스크를 유지할 수 없다.

```python
# Lambda — 불가능
def handler(event, context):
    asyncio.create_task(long_work())  # return 후 freeze, 실행 안 됨
    return {"statusCode": 200}
```

**해결:** SQS로 Lambda 실행 경계를 분리했다.

```
Ack Lambda:    이벤트 수신 → SQS 전송 → HTTP 200 반환  (3초 이내)
Worker Lambda: SQS 트리거 → AI Agent 실행             (최대 900초)
```

---

### 문제 2. Ack Lambda를 순수 라우터로 만들 수 없다

SQS 기준으로는 `Ack Lambda(Producer) → SQS → Worker Lambda(Consumer)` 구조다.
그런데 Slack의 `trigger_id`(modal 열기 토큰)는 발급 후 3초 안에 사용해야 만료되지 않는다.
SQS → Worker로 넘기면 도착 시점에 이미 만료되어 modal을 열 수 없다.

**해결:** Ack Lambda를 단순 라우터가 아닌 **Event Controller**로 정의했다.

| 처리 주체 | 기준 | 예시 |
|---|---|---|
| Ack Lambda 직접 | 3초 이내 완결 가능한 것 | modal 열기, cancel, ack |
| SQS → Worker | 3초 이내 완결 불가능한 것 | AI 분석, GitHub API |

---

### 문제 3. 여러 Lambda 실행에 걸친 상태 있는 대화를 어떻게 표현하나

워크플로우는 수 분에 걸친 사람-AI 협업이다.

```
/feat → AI 분석 → 사용자 결정 → AI 초안 생성 → 사용자 확인 → 이슈 생성
```

Lambda는 stateless다. WAIT 구간마다 종료되고 다음 사용자 액션 시 재시작된다.
이 흐름을 어떻게 코드로 표현할 것인가.

**해결:** Step Graph를 설계했다.

```python
GRAPH = {
    "find_relevant_bc": StepNode(
        step=FindRelevantBcStep(),
        control_signal=ControlSignal.CONTINUE,       # 다음 step으로 즉시 이동
        extract_input=lambda inst: ...,              # state에서 필요한 것만 꺼냄
        apply_output=lambda s, o: ...,               # 결과를 state에 반영
        on_continue="find_relevant_issue",
    ),
    "wait_issue_decision": StepNode(
        control_signal=ControlSignal.WAIT_FOR_USER,  # Slack 전송 후 Lambda 종료
        ...
    ),
}
```

`WorkflowRuntime`은 이 Graph를 읽어 실행하는 인터프리터다.
새 워크플로우 타입 추가 시 Graph만 정의하면 되고 Runtime은 건드리지 않는다.

**DynamoDB의 역할을 명확히 분리했다.**

- 다음 step 결정 → SQS 메시지의 `event_type` + `RESUME_MAP`
- DynamoDB → step 간 누적 컨텍스트(BC 목록, 이슈 목록, 초안) 보존만 담당

```
SQS message.type → RESUME_MAP → 다음 step  (라우팅)
DynamoDB         → state 로드               (컨텍스트)
```

---

### 문제 4. Lambda cold start가 Slack timeout을 유발하고 중복 실행으로 이어진다

```
Lambda cold start (최대 2~3초)
  → handler 실행 시간 3초 초과
  → Slack timeout → 동일 이벤트 재전송
  → SQS 중복 메시지 → Worker 중복 실행
  → 같은 워크플로우 두 번 처리
```

**해결:** 이중 dedup 레이어를 설계했다.

- **pending-action**: Slack `action_ts` 기반 DynamoDB 조건부 PutItem(`attribute_not_exists`).
  중복 버튼 클릭, Slack retry, SQS at-least-once 전부 차단. TTL 1h.
- **active-session**: `channel_id#user_id` 키로 동일 사용자의 동시 워크플로우 중복 차단. TTL 24h.

---

### 문제 5. Step Functions 없이 서버리스 상태 머신을 구현해야 한다

Slack 봇의 대화 모델은 본질적으로 상태 있는 장기 세션이다.
서버였다면 메모리와 백그라운드 스레드로 자연스럽게 처리되는 것들을 서버리스에서는 직접 구현해야 한다.

| 서버에서 자연스러운 것 | 서버리스 대체 |
|---|---|
| 메모리 상태 | DynamoDB |
| 백그라운드 스레드 | SQS + Worker Lambda |
| 세션 컨텍스트 유지 | GRAPH + RESUME_MAP |
| human-in-the-loop 대기 | WAIT 상태 + Lambda 종료 + 재트리거 |

Step Functions 도입을 검토했으나 월 30회 호출 규모에서는 오버엔지니어링이다.
SQS + DynamoDB 직접 구현으로 비용 $0, 개발 속도, 낮은 복잡도를 모두 확보했다.

---

## 설계 원칙

**패키지 간 의존성은 인터페이스만.**
`IWorkflowInstanceRepository`, `IQueueSender`, `IAgent` 등 핵심 경계마다 인터페이스를 정의했다.
로컬 개발 시 메모리 구현체로 교체해 AWS 없이 전체 흐름을 실행한다.

**확장에 열리고 수정에 닫힌 구조.**
새 워크플로우 타입(feat/refactor/fix)은 GRAPH와 state 등록만으로 추가된다.
WorkflowRuntime, DynamoDB 스키마, SQS 구조는 건드리지 않는다.

---

## 인프라

Terraform 관리. GitHub Actions OIDC 기반 배포 (시크릿 키 없음).

- Lambda arm64 (Graviton) — x86 대비 성능 향상, 약 20% 비용 절감
- S3 SHA 키 배포 + Parameter Store 포인터 — 롤백 시 Parameter 값만 변경
- DynamoDB 3테이블 TTL 관리 (workflow 24h · pending-action 1h · active-session 24h)
- SQS DLQ maxReceiveCount=2, visibility timeout=900s

---

## 남은 한계

| 한계 | 근본 원인 |
|---|---|
| Worker 실패 시 사용자 알림 없음 | DLQ CloudWatch Alarm 미구현 |
| step 실패 시 앞 step부터 재실행 | 한 Worker 실행 안에 여러 step이 묶임 |
| cold start로 인한 Slack timeout 가능성 | Lambda 비상시 기동 |
