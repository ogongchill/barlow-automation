# Barlow Automation — 인프라 설정 가이드

AWS를 어느 정도 알고 있는 사람을 대상으로 한 단계별 배포 가이드.

**역할 분리 원칙:**
- **Terraform**: 인프라 리소스 관리 (DynamoDB, SQS, IAM, Lambda 설정)
- **GitHub Actions**: 코드 배포 (`update-function-code`)

인프라는 거의 바뀌지 않고 코드는 자주 바뀌므로 분리한다.

---

## 전체 순서 요약

```
1. 사전 준비 (AWS CLI, Terraform, Python)
2. Terraform 디렉토리 생성
3. Terraform apply (AWS 리소스 일괄 생성) — 최초 1회
4. GitHub Secrets 등록
5. GitHub Actions로 코드 배포
6. Slack 앱 설정
7. 동작 확인
```

---

## Step 1. 사전 준비

### 1-1. 필수 도구 설치 확인

```bash
aws --version       # AWS CLI v2 이상
terraform --version # Terraform v1.5 이상
python --version    # Python 3.12 이상
```

### 1-2. AWS 자격증명 설정

```bash
aws configure
# AWS Access Key ID: <your-key>
# AWS Secret Access Key: <your-secret>
# Default region name: ap-northeast-2
# Default output format: json
```

자격증명 확인:
```bash
aws sts get-caller-identity
```

### 1-3. 필요한 API 키/토큰 준비

| 항목 | 발급처 | 비고 |
|------|--------|------|
| `SLACK_BOT_TOKEN` | Slack API → OAuth & Permissions | `xoxb-` 로 시작 |
| `SLACK_SIGNING_SECRET` | Slack API → Basic Information | |
| `OPENAI_API_KEY` | platform.openai.com | Agent 실행용 |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Agent 실행용 |
| `GITHUB_TOKEN` | GitHub → Settings → Developer Settings → PAT | `repo`, `read:org` 스코프 |
| `GITHUB_OWNER` | 대상 GitHub 레포 owner (org 또는 user) | |
| `GITHUB_REPO` | 대상 GitHub 레포 이름 | |

---

## Step 2. Terraform 디렉토리 생성

프로젝트 루트 아래에 `terraform/` 디렉토리를 만든다.

```bash
mkdir -p terraform
```

아래 파일들을 순서대로 생성한다.

---

### terraform/main.tf

```hcl
terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # 팀 작업 시 S3 backend 사용 권장
  # backend "s3" {
  #   bucket = "my-terraform-state"
  #   key    = "barlow/terraform.tfstate"
  #   region = "ap-northeast-2"
  # }
}

provider "aws" {
  region = var.aws_region
}

locals {
  common_tags = {
    Project     = "barlow-automation"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
```

---

### terraform/variables.tf

```hcl
variable "aws_region" {
  type    = string
  default = "ap-northeast-2"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "slack_bot_token" {
  type      = string
  sensitive = true
}

variable "slack_signing_secret" {
  type      = string
  sensitive = true
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
}

variable "github_token" {
  type      = string
  sensitive = true
}

variable "github_owner" {
  type = string
}

variable "github_repo" {
  type = string
}
```

---

### terraform/terraform.tfvars

> **주의**: 이 파일은 `.gitignore`에 추가해야 한다. 시크릿 값이 포함된다.

```hcl
aws_region  = "ap-northeast-2"
environment = "prod"

github_owner = "your-org"
github_repo  = "your-repo"

slack_bot_token      = "xoxb-..."
slack_signing_secret = "..."
openai_api_key       = "sk-..."
anthropic_api_key    = "sk-ant-..."
github_token         = "ghp_..."
```

`.gitignore`에 추가:
```
terraform/*.tfvars
terraform/.terraform/
terraform/terraform.tfstate*
dist/
```

---

### terraform/dynamodb.tf

```hcl
resource "aws_dynamodb_table" "workflow" {
  name         = "barlow-workflow"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "workflow_id"

  attribute {
    name = "workflow_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}

resource "aws_dynamodb_table" "pending_action" {
  name         = "barlow-pending-action"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}

resource "aws_dynamodb_table" "active_session" {
  name         = "barlow-active-session"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}
```

---

### terraform/sqs.tf

```hcl
resource "aws_sqs_queue" "dlq" {
  name                      = "barlow-queue-dlq"
  message_retention_seconds = 1209600  # 14일
  tags                      = local.common_tags
}

resource "aws_sqs_queue" "main" {
  name                       = "barlow-queue"
  visibility_timeout_seconds = 900    # Worker Lambda timeout과 동일하게 맞춤
  message_retention_seconds  = 86400  # 24시간

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 2
  })

  tags = local.common_tags
}
```

---

### terraform/iam.tf

```hcl
# ─── Ack Lambda Role ───────────────────────────────────────────────────────────

resource "aws_iam_role" "ack" {
  name = "barlow-ack-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "ack" {
  name = "barlow-ack-policy"
  role = aws_iam_role.ack.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.main.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ─── Worker Lambda Role ────────────────────────────────────────────────────────

resource "aws_iam_role" "worker" {
  name = "barlow-worker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "worker" {
  name = "barlow-worker-policy"
  role = aws_iam_role.worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.main.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          aws_dynamodb_table.workflow.arn,
          aws_dynamodb_table.pending_action.arn,
          aws_dynamodb_table.active_session.arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ─── GitHub Actions OIDC 배포 Role ────────────────────────────────────────────
# 시크릿 키 없이 GitHub Actions가 직접 assume하는 Role

data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "deployer" {
  name = "barlow-deployer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:your-org/barlow-automation:ref:refs/heads/master"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "deployer" {
  name = "barlow-deployer-policy"
  role = aws_iam_role.deployer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = "arn:aws:s3:::barlow-deploy-bucket/barlow/*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction"
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:barlow-ack",
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:barlow-worker"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:PutParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/barlow/deploy/*"
      }
    ]
  })
}
```

---

### terraform/lambda.tf

> Terraform은 Lambda 설정(메모리, 타임아웃, 환경변수, 트리거)만 관리한다.
> 코드 배포는 GitHub Actions가 담당한다.
> 최초 `terraform apply` 시에는 placeholder zip으로 함수를 생성하고, 이후 Actions가 실제 코드를 올린다.

```hcl
# ─── 최초 배포용 placeholder zip ──────────────────────────────────────────────
# terraform apply 시 함수 생성을 위한 빈 zip (실제 코드는 Actions가 올림)

data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  source {
    content  = "# placeholder"
    filename = "handler.py"
  }
}

# ─── Ack Lambda ───────────────────────────────────────────────────────────────

resource "aws_lambda_function" "ack" {
  function_name = "barlow-ack"
  role          = aws_iam_role.ack.arn
  handler       = "src.controller.lambda_ack.handler"
  runtime       = "python3.12"
  timeout       = 29
  memory_size   = 256

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  # GitHub Actions가 update-function-code로 코드를 교체하므로
  # terraform plan에서 코드 변경을 무시한다
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }

  environment {
    variables = {
      SLACK_BOT_TOKEN      = var.slack_bot_token
      SLACK_SIGNING_SECRET = var.slack_signing_secret
      SQS_QUEUE_URL        = aws_sqs_queue.main.url
      GITHUB_TOKEN         = var.github_token
      GITHUB_OWNER         = var.github_owner
      GITHUB_REPO          = var.github_repo
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function_url" "ack" {
  function_name      = aws_lambda_function.ack.function_name
  authorization_type = "NONE"
}

resource "aws_cloudwatch_log_group" "ack" {
  name              = "/aws/lambda/barlow-ack"
  retention_in_days = 14
  tags              = local.common_tags
}

# ─── Worker Lambda ────────────────────────────────────────────────────────────

resource "aws_lambda_function" "worker" {
  function_name = "barlow-worker"
  role          = aws_iam_role.worker.arn
  handler       = "src.app.handlers.step_worker_handler.handler"
  runtime       = "python3.12"
  timeout       = 900
  memory_size   = 512

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }

  environment {
    variables = {
      SLACK_BOT_TOKEN      = var.slack_bot_token
      SLACK_SIGNING_SECRET = var.slack_signing_secret
      SQS_QUEUE_URL        = aws_sqs_queue.main.url
      OPENAI_API_KEY       = var.openai_api_key
      ANTHROPIC_API_KEY    = var.anthropic_api_key
      GITHUB_TOKEN         = var.github_token
      GITHUB_OWNER         = var.github_owner
      GITHUB_REPO          = var.github_repo
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_event_source_mapping" "worker_sqs" {
  event_source_arn = aws_sqs_queue.main.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1  # 반드시 1 — 멱등성 보장
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/barlow-worker"
  retention_in_days = 30
  tags              = local.common_tags
}
```

---

### terraform/outputs.tf

```hcl
output "ack_function_url" {
  description = "Slack에 등록할 Request URL"
  value       = aws_lambda_function_url.ack.function_url
}

output "sqs_queue_url" {
  value = aws_sqs_queue.main.url
}

output "deployer_role_arn" {
  description = "deploy.yml role-to-assume에 이미 하드코딩 — 확인용"
  value       = aws_iam_role.deployer.arn
}
```

---

## Step 3. Terraform으로 AWS 리소스 생성

```bash
cd terraform

# 초기화 (최초 1회)
terraform init

# 변경사항 미리 보기
terraform plan -var-file="terraform.tfvars"

# 적용 (실제 리소스 생성)
terraform apply -var-file="terraform.tfvars"
```

`apply` 완료 후 출력 예시:
```
Outputs:
ack_function_url           = "https://xxxxxxxx.lambda-url.ap-northeast-2.on.aws/"
deployer_access_key_id     = "AKIA..."
deployer_secret_access_key = <sensitive>
```

`ack_function_url`과 deployer 키를 복사해 둔다.

---

## Step 4. GitHub Secrets 등록

GitHub 레포 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 | 비고 |
|------------|-----|------|
| `AWS_REGION` | `ap-northeast-2` | |

Role ARN은 `deploy.yml`에 하드코딩되어 있어 Secret 불필요. 시크릿 키 없음.

---

## Step 5. GitHub Actions 워크플로우

`.github/workflows/deploy.yml` 파일을 생성한다.

```yaml
name: Deploy Lambda

on:
  push:
    branches:
      - master
    paths:
      - 'src/**'
      - 'requirements.txt'

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Build package
        run: |
          mkdir -p dist/package
          pip install -r requirements.txt -t dist/package/ --quiet
          cp -r src dist/package/
          cd dist/package && zip -r ../lambda.zip . -q

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Deploy Ack Lambda
        run: |
          aws lambda update-function-code \
            --function-name barlow-ack \
            --zip-file fileb://dist/lambda.zip

      - name: Deploy Worker Lambda
        run: |
          aws lambda update-function-code \
            --function-name barlow-worker \
            --zip-file fileb://dist/lambda.zip
```

**트리거 조건**: `master` 브랜치에 `src/` 또는 `requirements.txt`가 변경된 push가 들어올 때만 실행.

---

## Step 6. Slack 앱 설정

[Slack API 콘솔](https://api.slack.com/apps)에서 앱을 선택한 뒤 아래를 순서대로 설정한다.

### 6-1. Interactivity & Shortcuts 설정

좌측 메뉴 → **Interactivity & Shortcuts**

- Interactivity: **On**
- Request URL: `https://xxxxxxxx.lambda-url.ap-northeast-2.on.aws/` (Step 3 출력값)

**Save Changes** 클릭.

### 6-2. Slash Commands 등록

좌측 메뉴 → **Slash Commands** → **Create New Command**

| Command | Request URL | Short Description |
|---------|-------------|-------------------|
| `/feat` | Function URL | 기능 요청 이슈 생성 |
| `/refactor` | Function URL | 리팩토링 이슈 생성 |
| `/fix` | Function URL | 버그 수정 이슈 생성 |
| `/drop` | Function URL | 진행 중인 워크플로우 취소 |

### 6-3. OAuth Scopes 확인

좌측 메뉴 → **OAuth & Permissions** → **Bot Token Scopes**

| Scope | 설명 |
|-------|------|
| `commands` | 슬래시 커맨드 수신 |
| `chat:write` | 채널 메시지 전송/업데이트 |
| `views:open` | Modal 열기 |
| `views:push` | Modal 스택 추가 |

스코프가 없으면 추가 후 **Reinstall to Workspace** 클릭.

---

## Step 7. 동작 확인

### 7-1. Actions 배포 확인

GitHub → **Actions** 탭에서 `Deploy Lambda` 워크플로우가 성공했는지 확인.

### 7-2. /feat 커맨드 테스트

Slack에서 `/feat` 입력 → Modal이 열리면 정상.
Modal 제출 → "요청을 수신했습니다. 분석을 시작합니다... ⏳" 메시지가 오면 Ack Lambda 정상 동작.

### 7-3. CloudWatch 로그 확인

```bash
aws logs tail /aws/lambda/barlow-ack --follow
aws logs tail /aws/lambda/barlow-worker --follow
```

Worker Lambda 로그에서 step 실행 흐름이 보여야 한다:
```
step | executing workflow_id=xxx step=find_relevant_bc
step | executing workflow_id=xxx step=find_relevant_issue
step | waiting workflow_id=xxx step=wait_issue_decision
```

### 7-4. 문제 발생 시 체크리스트

| 증상 | 확인 항목 |
|------|----------|
| Actions 실패 | AWS_ACCESS_KEY_ID/SECRET 등록 여부, IAM 권한 (`lambda:UpdateFunctionCode`) |
| Modal이 안 열림 | Slack Interactivity Request URL, Ack Lambda timeout (29s) |
| "요청 수신" 메시지가 안 옴 | SQS SendMessage IAM 권한, SLACK_BOT_TOKEN 환경변수 |
| Worker Lambda가 안 실행됨 | SQS 트리거 batch_size=1 확인 |
| DynamoDB 에러 | Worker Lambda IAM 정책, 테이블 이름 오타 |

---

## 인프라 변경 시 (Terraform)

Lambda 메모리, 타임아웃, 환경변수 등 인프라 설정이 바뀔 때만 Terraform을 실행한다.

```bash
cd terraform
terraform apply -var-file="terraform.tfvars"
```

코드만 바꿀 때는 그냥 `master`에 push하면 Actions가 자동 배포한다.

---

## 리소스 삭제

```bash
cd terraform
terraform destroy -var-file="terraform.tfvars"
```

DynamoDB 데이터도 함께 삭제되므로 주의.
