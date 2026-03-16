# AWS 인프라 설정 가이드

barlow-automation 배포에 필요한 AWS 리소스 목록 및 설정값 정리.

---

## 리소스 구성 요약

```
Slack App
    │ HTTPS (Function URL)
    ▼
Ack Lambda (Function URL)  ──────────► SQS Queue (barlow-queue)
(src/controller/lambda_ack.py)                  │
                                                 ▼
                                       Worker Lambda
                                       (src/lambda_worker.py)
                                            │         │
                                            ▼         ▼
                                     DynamoDB      DynamoDB
                                   barlow-pending  barlow-idempotency
```

---

## 1. DynamoDB 테이블

### `barlow-pending`

이슈 초안 대기 레코드 저장 (사용자 검토 중인 이슈 컨텍스트).

| 항목 | 값 |
|------|-----|
| 테이블 이름 | `barlow-pending` |
| 파티션 키 | `pk` (String) — Slack message_ts |
| 정렬 키 | 없음 |
| TTL 속성 | `ttl` (Number) — Unix timestamp, 24시간 후 자동 삭제 |
| 용량 모드 | On-Demand (PAY_PER_REQUEST) |
| 암호화 | AWS 관리 키 (기본값) |

**액세스 패턴**

| 작업 | 조건 |
|------|------|
| PutItem | 이슈 초안 저장 (pipeline_start, rotate) |
| GetItem | pk = message_ts |
| DeleteItem | pk = message_ts |
| TransactWriteItems | 새 레코드 PutItem + 기존 레코드 DeleteItem (rotate) |

**속성 목록**

```
pk              String    Slack message_ts (PK)
subcommand      String    "feat" | "refactor" | "fix"
user_id         String    Slack user ID
channel_id      String    Slack channel ID
user_message    String    Modal 입력 to_prompt() 결과
inspector_output String   Inspector Agent 출력 JSON
typed_output    String    이슈 템플릿 JSON (FeatTemplate 등)
ttl             Number    Unix timestamp (TTL 속성)
```

---

### `barlow-idempotency`

SQS 메시지 중복 처리 방지 (dedup_id 기반).

| 항목 | 값 |
|------|-----|
| 테이블 이름 | `barlow-idempotency` |
| 파티션 키 | `pk` (String) — dedup_id (view_id 또는 action_ts) |
| 정렬 키 | 없음 |
| TTL 속성 | `ttl` (Number) — Unix timestamp, 1시간 후 자동 삭제 |
| 용량 모드 | On-Demand (PAY_PER_REQUEST) |
| 암호화 | AWS 관리 키 (기본값) |

**액세스 패턴**

| 작업 | 조건 |
|------|------|
| PutItem (조건부) | `attribute_not_exists(pk)` — 중복 시 ConditionalCheckFailedException |
| UpdateItem | pk = dedup_id, status → "DONE" |

**속성 목록**

```
pk      String    dedup_id (PK)
status  String    "PROCESSING" | "DONE"
ttl     Number    Unix timestamp (TTL 속성)
```

---

## 2. SQS 큐

| 항목 | 값 |
|------|-----|
| 큐 이름 | `barlow-queue` |
| 큐 타입 | Standard (순서 보장 불필요) |
| Visibility Timeout | 900초 (15분 — Worker Lambda 최대 실행 시간과 동일) |
| Message Retention | 86400초 (24시간) |
| Dead Letter Queue | `barlow-queue-dlq` 연결 권장 (maxReceiveCount: 2) |

**DLQ 설정 (`barlow-queue-dlq`)**

| 항목 | 값 |
|------|-----|
| 큐 타입 | Standard |
| Message Retention | 1209600초 (14일) |

> Visibility Timeout은 Worker Lambda timeout 이상이어야 합니다.
> Lambda가 처리 중인 메시지가 다시 큐에 노출되어 중복 실행되는 것을 방지합니다.

---

## 3. Lambda 함수

### Ack Lambda

| 항목 | 값 |
|------|-----|
| 함수 이름 | `barlow-ack` |
| 진입점 | `src/controller/lambda_ack.handler` |
| 런타임 | Python 3.12 |
| 메모리 | 256 MB |
| 타임아웃 | 29초 (Slack 3초 응답 + 여유) |
| 트리거 | Lambda Function URL |

**환경 변수**

```
SLACK_BOT_TOKEN       xoxb-...
SLACK_SIGNING_SECRET  ...
OPENAI_API_KEY        sk-...
ANTHROPIC_API_KEY     sk-ant-...
GITHUB_TOKEN          ghp_...
SQS_QUEUE_URL         https://sqs.<region>.amazonaws.com/<account-id>/barlow-queue
TARGET_REPO           owner/repo
```

**IAM 권한**

```json
{
  "Effect": "Allow",
  "Action": [
    "sqs:SendMessage"
  ],
  "Resource": "arn:aws:sqs:<region>:<account-id>:barlow-queue"
}
```

---

### Worker Lambda

| 항목 | 값 |
|------|-----|
| 함수 이름 | `barlow-worker` |
| 진입점 | `src/lambda_worker.handler` |
| 런타임 | Python 3.12 |
| 메모리 | 512 MB |
| 타임아웃 | 900초 (15분) |
| 트리거 | SQS (barlow-queue), batch size: 1 |

**환경 변수** (Ack Lambda와 동일)

```
SLACK_BOT_TOKEN
SLACK_SIGNING_SECRET
OPENAI_API_KEY
ANTHROPIC_API_KEY
GITHUB_TOKEN
SQS_QUEUE_URL
TARGET_REPO
```

**IAM 권한**

```json
[
  {
    "Effect": "Allow",
    "Action": [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ],
    "Resource": "arn:aws:sqs:<region>:<account-id>:barlow-queue"
  },
  {
    "Effect": "Allow",
    "Action": [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:DeleteItem",
      "dynamodb:UpdateItem",
      "dynamodb:TransactWriteItems"
    ],
    "Resource": [
      "arn:aws:dynamodb:<region>:<account-id>:table/barlow-pending",
      "arn:aws:dynamodb:<region>:<account-id>:table/barlow-idempotency"
    ]
  }
]
```

> SQS 트리거의 `batch size: 1` 설정이 중요합니다.
> 하나의 Lambda 실행이 하나의 SQS 메시지만 처리하도록 보장하여
> 멱등성 로직이 정확히 동작합니다.

---

## 4. Lambda Function URL (Ack Lambda)

API Gateway 없이 Lambda에 직접 HTTPS 엔드포인트를 부여합니다.

| 항목 | 값 |
|------|-----|
| Auth 타입 | `NONE` — Slack 서명 검증은 Bolt 미들웨어가 처리 |
| CORS | 비활성화 (Slack 서버가 직접 호출, 브라우저 아님) |
| URL 형식 | `https://<url-id>.lambda-url.<region>.on.aws/` |

**이벤트 형식 (Lambda Function URL v2)**

```json
{
  "version": "2.0",
  "requestContext": {
    "http": {
      "method": "POST",
      "path": "/"
    }
  },
  "headers": {
    "content-type": "application/x-www-form-urlencoded",
    "x-slack-request-timestamp": "...",
    "x-slack-signature": "v0=..."
  },
  "body": "command=%2Ffeat&...",
  "isBase64Encoded": false
}
```

Bolt의 `AsyncBoltRequest`가 `body`와 `headers`를 직접 추출하므로
API Gateway 없이도 동작합니다.

---

## 5. Slack 앱 설정

Function URL 발급 후 [Slack API 콘솔](https://api.slack.com/apps)에서 설정.

### Interactivity & Shortcuts

```
Request URL: https://<url-id>.lambda-url.<region>.on.aws/
```

Modal 제출, Block Action 버튼 클릭 이벤트를 수신합니다.

### Slash Commands

각 커맨드마다 동일한 Request URL 등록.

| Command | Request URL |
|---------|-------------|
| `/feat` | `https://<url-id>.lambda-url.<region>.on.aws/` |
| `/refactor` | 동일 |
| `/fix` | 동일 |

### OAuth Scopes (Bot Token)

| Scope | 용도 |
|-------|------|
| `commands` | 슬래시 커맨드 수신 |
| `chat:write` | 메시지 전송 및 업데이트 |
| `views:open` | Modal 오픈 |
| `views:push` | Modal 스택 추가 |

---

## 6. Secrets Manager (선택)

환경 변수에 민감 정보를 직접 넣는 대신 AWS Secrets Manager 사용 권장.

| 시크릿 이름 | 포함 키 |
|------------|--------|
| `barlow/slack` | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` |
| `barlow/ai` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| `barlow/github` | `GITHUB_TOKEN` |

Lambda 실행 역할에 `secretsmanager:GetSecretValue` 권한 추가 필요.

---

## 7. 배포 체크리스트

```
[ ] DynamoDB 테이블 2개 생성 (barlow-pending, barlow-idempotency)
    [ ] TTL 활성화 (ttl 속성 지정)

[ ] SQS 큐 생성 (barlow-queue)
    [ ] Visibility Timeout = 900초
    [ ] DLQ 연결 (barlow-queue-dlq, maxReceiveCount: 2)

[ ] Lambda 함수 2개 배포
    [ ] barlow-ack (진입점: src/controller/lambda_ack.handler)
    [ ] barlow-worker (진입점: src/lambda_worker.handler)
    [ ] 환경 변수 설정
    [ ] IAM 역할 및 정책 연결

[ ] Ack Lambda Function URL 활성화
    [ ] Auth 타입: NONE
    [ ] URL 확인 (https://<url-id>.lambda-url.<region>.on.aws/)

[ ] SQS 트리거 등록
    [ ] barlow-queue → barlow-worker (batch size: 1)

[ ] Slack 앱 설정
    [ ] Interactivity Request URL → Function URL 등록
    [ ] Slash Commands Request URL 등록 (/feat, /refactor, /fix)
    [ ] Bot OAuth Scopes 확인 및 앱 재설치

[ ] 동작 확인
    [ ] /feat 커맨드 → Modal 오픈
    [ ] Modal 제출 → SQS 메시지 전송 확인 (CloudWatch Logs)
    [ ] Worker Lambda 실행 → Slack 메시지 수신
```
