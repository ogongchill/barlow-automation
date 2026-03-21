# Barlow Automation — 인프라 설계 문서

Terraform 작성자를 위한 리소스 설계 문서.
실제 코드는 이 문서를 기반으로 작성한다.

---

## 전체 아키텍처

```
Slack
  │ slash command / modal submit / button click
  ▼
Lambda Function URL (barlow-slack-ack)          ← 29초 타임아웃 (Slack 3초 ack 제한)
  │ Slack 서명 검증 (Bolt)
  │ SQS 메시지 전송
  ▼
SQS Queue (barlow-queue)
  │ trigger (batch size = 1)
  ▼
Lambda (barlow-automation-worker)                    ← 900초 타임아웃 (AI agent 실행)
  │ DynamoDB read/write
  │ Slack API 호출
  │ GitHub REST API 호출
  ▼
DynamoDB (3개 테이블)
```

---

## Lambda

### barlow-slack-ack

| 항목 | 값 |
|------|-----|
| Runtime | python3.12 |
| Handler | `src.controller.lambda_ack.handler` |
| Timeout | **29초** (Slack 요구사항 — 3초 내 ack, 나머지는 SQS로 위임) |
| Memory | 256 MB |
| Trigger | Lambda Function URL |
| Function URL auth | NONE (Slack 서명 검증을 Bolt 미들웨어가 담당) |

환경변수:
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SQS_QUEUE_URL`
- `GITHUB_TOKEN`
- `TARGET_REPO`

### barlow-automation-worker

| 항목 | 값 |
|------|-----|
| Runtime | python3.12 |
| Handler | `src.app.handlers.step_worker_handler.handler` |
| Timeout | **900초** (AI agent + GitHub MCP 호출 포함, 최대 15분) |
| Memory | 512 MB |
| Trigger | SQS (barlow-queue) |

환경변수:
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SQS_QUEUE_URL`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GITHUB_TOKEN`
- `TARGET_REPO`

### 코드 배포 방식

Terraform은 Lambda **설정만** 관리한다. 코드 배포는 GitHub Actions가 담당.

- 최초 `terraform apply` 시 placeholder zip으로 함수 생성
- 이후 Actions가 `update-function-code`로 실제 코드 교체
- Terraform이 코드 변경에 반응하지 않도록 `lifecycle.ignore_changes` 적용 필요
  - 대상: `filename`, `source_code_hash`

---

## SQS

### barlow-queue (메인 큐)

| 항목 | 값 | 이유 |
|------|-----|------|
| Visibility Timeout | **900초** | Worker Lambda timeout과 반드시 동일해야 함. 짧으면 처리 중인 메시지가 재전송됨 |
| Message Retention | 86400초 (24h) | 워크플로우 최대 수명 기준 |
| Batch Size (Event Source) | **1** | 멱등성 보장 필수. 2 이상이면 동일 워크플로우가 병렬 실행될 수 있음 |
| DLQ | barlow-queue-dlq 연결 | maxReceiveCount = 2 |

### barlow-queue-dlq (Dead Letter Queue)

| 항목 | 값 |
|------|-----|
| Message Retention | 1209600초 (14일) |

DLQ 메시지 = 2회 처리 실패한 이벤트. 수동 확인 후 재처리 또는 폐기.

---

## DynamoDB

### barlow-workflow

워크플로우 인스턴스 저장. 각 사용자 요청당 하나의 레코드.

| 항목 | 값 |
|------|-----|
| PK | `workflow_id` (String) |
| Billing | PAY_PER_REQUEST |
| TTL | `ttl` 컬럼 (Unix timestamp, 생성 시 +24h) |

### barlow-pending-action

SQS 이벤트 멱등성 처리. 동일 메시지 중복 처리 방지.

| 항목 | 값 |
|------|-----|
| PK | `pk` (String) — dedup_id (Slack view_id 또는 action_ts) |
| Billing | PAY_PER_REQUEST |
| TTL | `ttl` 컬럼 (Unix timestamp, 생성 시 +1h) |

핵심 동작: `attribute_not_exists(pk)` 조건부 PutItem. 이미 존재하면 중복 처리 skip.

### barlow-active-session

채널+유저 단위 활성 워크플로우 추적. 동일 사용자가 같은 채널에서 워크플로우를 중복 시작하지 못하게 막음.

| 항목 | 값 |
|------|-----|
| PK | `pk` (String) — `{channel_id}#{user_id}` |
| Billing | PAY_PER_REQUEST |
| TTL | `ttl` 컬럼 (Unix timestamp, 생성 시 +24h) |

---

## IAM

### barlow-slack-ack-role

barlow-slack-ack Lambda 실행 역할.

필요 권한:
- `sqs:SendMessage` — barlow-queue ARN 한정
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

### barlow-automation-worker-role

barlow-automation-worker Lambda 실행 역할.

필요 권한:
- `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` — barlow-queue ARN 한정
- `dynamodb:PutItem`, `dynamodb:GetItem`, `dynamodb:DeleteItem`, `dynamodb:UpdateItem` — 3개 테이블 ARN 한정
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

### barlow-deployer-role

GitHub Actions OIDC용 역할. 시크릿 키 없이 assume.

Trust Policy 조건:
- Federated: GitHub OIDC Provider (`token.actions.githubusercontent.com`)
- `aud`: `sts.amazonaws.com`
- `sub`: `repo:{org}/{repo}:ref:refs/heads/master` (master 브랜치 push만 허용)

필요 권한:
- `s3:PutObject` — `barlow-deploy-bucket/barlow/automation/*` 한정
- `lambda:UpdateFunctionCode`, `lambda:GetFunction` — barlow-slack-ack, barlow-automation-worker ARN 한정
- `ssm:PutParameter` — `/barlow/deploy/*` 한정

OIDC Provider 설정값:
- URL: `https://token.actions.githubusercontent.com`
- Client ID: `sts.amazonaws.com`
- Thumbprint: `6938fd4d98bab03faadb97b34396831e3780aea1`

> 동일 AWS 계정에 GitHub OIDC Provider가 이미 등록되어 있으면 중복 생성 불가. 기존 Provider를 data source로 참조할 것.

---

## S3 (배포 아티팩트)

버킷: `barlow-deploy-bucket` (기존 버킷 재사용 — Terraform으로 새로 생성하지 않음)

| 항목 | 값 |
|------|-----|
| Versioning | 불필요 (key에 SHA 포함으로 버전 관리) |
| 배포 경로 | `barlow/automation/lambda-{git-sha}.zip` |

커밋마다 별도 파일로 쌓이므로 S3 Versioning 없이도 전체 배포 이력이 유지됨.
오래된 파일은 S3 Lifecycle 정책으로 주기적 삭제 권장 (예: 30일 이상 된 `barlow/automation/lambda-*.zip`).

---

## Parameter Store (배포 상태 포인터)

현재 Lambda에 배포된 버전을 추적하는 포인터. Terraform이 읽지 않으며 배포 상태 확인 및 롤백 용도로만 사용.

| Parameter | Type | 값 예시 |
|-----------|------|--------|
| `/barlow/deploy/current-key` | String | `barlow/automation/lambda-f648d7c.zip` |
| `/barlow/deploy/current-sha` | String | `f648d7c...` |

GitHub Actions가 Lambda 배포 완료 후 자동 업데이트.

**롤백 절차:**
```bash
# 1. 현재 배포 확인
aws ssm get-parameter --name /barlow/deploy/current-sha

# 2. S3에서 이전 버전 목록 확인
aws s3 ls s3://barlow-deploy-bucket/barlow/automation/

# 3. Lambda에 이전 버전 반영 (핵심 — Parameter Store만 바꿔서는 Lambda에 반영 안 됨)
OLD_SHA="이전커밋SHA"
aws lambda update-function-code \
  --function-name barlow-slack-ack \
  --s3-bucket barlow-deploy-bucket \
  --s3-key barlow/automation/lambda-${OLD_SHA}.zip

aws lambda update-function-code \
  --function-name barlow-automation-worker \
  --s3-bucket barlow-deploy-bucket \
  --s3-key barlow/automation/lambda-${OLD_SHA}.zip

# 4. Parameter Store 동기화 (추적 목적)
aws ssm put-parameter --name /barlow/deploy/current-sha --value $OLD_SHA --overwrite
```

---

## CloudWatch Logs

| 로그 그룹 | Retention |
|----------|-----------|
| `/aws/lambda/barlow-slack-ack` | 14일 |
| `/aws/lambda/barlow-automation-worker` | 30일 (AI agent 트레이스 포함) |

---

## 주요 제약 및 주의사항

**SQS Visibility Timeout = Lambda Timeout**
두 값이 다르면 장애 발생. Lambda가 처리 중인데 메시지가 다시 큐에 나타나 중복 실행됨.

**SQS Batch Size = 1**
멱등성 처리(barlow-pending-action)가 메시지 단위로 동작함. 2 이상이면 같은 워크플로우가 병렬로 실행될 수 있음.

**Lambda Function URL**
barlow-slack-ack만 Function URL이 필요함. barlow-automation-worker는 SQS 트리거만 사용.

**Terraform이 코드를 관리하지 않음**
`lifecycle.ignore_changes`로 코드 관련 속성을 무시해야 함. 그렇지 않으면 `terraform plan`마다 코드 변경을 감지해 덮어씀.

**GitHub OIDC Provider 중복 주의**
AWS 계정당 동일 URL의 OIDC Provider는 하나만 존재 가능. 기존에 등록된 경우 `data "aws_iam_openid_connect_provider"`로 참조.
