# Ack Lambda 성능 분석 및 최적화

---

## 측정 환경

- Lambda: `barlow-slack-ack` (arm64 / Graviton, 256MB)
- 트리거: Slack `/feat` 슬래시 커맨드 → Lambda Function URL
- 측정 방법: CloudWatch REPORT 로그

---

## 기준선 (Before — 2026-03-29)

### Cold start (n=2)

| 회차 | Init Duration | Handler Duration | 합계 |
|---|---|---|---|
| 1 | 918ms | 674ms | 1,593ms |
| 2 | 897ms | 625ms | 1,523ms |
| **평균** | **908ms** | **650ms** | **1,558ms** |

### Warm start (n=2)

| 회차 | Handler Duration |
|---|---|
| 1 | 330ms |
| 2 | 301ms |
| **평균** | **316ms** |

### 비교

| 구분 | Init | Handler | 합계 |
|---|---|---|---|
| Cold start | 908ms | 650ms | **1,558ms** |
| Warm start | — | 316ms | **316ms** |
| 차이 | +908ms | +334ms | **+1,242ms** |

Init Duration 편차 ±10ms → 패키지 크기 기반, 재현 가능한 수치

---

## 문제 분석

### Slack 3초 제약과의 관계

```
warm: 316ms + 네트워크 ~150ms  = ~466ms    ✓ 안전
cold: 1558ms + 네트워크 ~150ms = ~1708ms   △ margin 1.3초
```

Slack API(views_open) 응답이 300ms 이상 지연되면 cold start 총합이 2초를 초과한다.

### 근본 구조

```
월 30회 호출 → 호출 간격 길다 → 대부분 cold start
cold start → Slack 3초 초과 위험 → timeout → retry → dedup 필요
```

dedup 레이어(pending-action, active-session)가 존재하는 근본 원인 중 하나가 cold start다.

### Handler Duration 분해

```
cold handler 650ms:
  views_open (Slack API):        ~200ms
  SQS send (첫 TCP connection):  ~300ms   ← warm 대비 ~3배
  routing / ack:                 ~150ms

warm handler 316ms:
  views_open (Slack API):        ~180ms
  SQS send (connection 재사용):  ~100ms
  routing / ack:                  ~36ms
```

cold handler의 SQS 오버헤드 +200ms는 boto3 첫 TCP connection 비용이다.

---

## 최적화 과정

### Step 1 — Lambda 진입점 분리 (완료)

**문제**: Lambda 진입점이 Slack Bolt에 종속되어 있어 EventBridge ping이 서명 검증에 막힌다.

```python
# Before — 모든 이벤트가 Bolt를 통과
def handler(event, context):
    return asyncio.run(_dispatch(event))

# After — 이벤트 유형별 분기
def handler(event, context):
    if event.get("source") == "aws.events":
        _get_app()  # Bolt 초기화까지 완료
        return {"statusCode": 200, "body": "warm"}
    return asyncio.run(_dispatch(event))
```

**Lazy init 병행 적용**: 모듈 레벨 Bolt/boto3 초기화를 `_get_app()`으로 지연.
ping이 `_get_app()`을 호출해 Bolt 초기화까지 완료하므로 이후 Slack 요청은 warm handler(316ms)만 소요.

커밋: `83058ea`

---

### Step 2 — 패키지 분리 (완료)

**문제**: Ack Lambda와 Worker Lambda가 동일한 zip을 사용.
Ack Lambda에 불필요한 AI SDK가 포함되어 패키지가 비대함.

**원인 분석 — import 체인 추적:**

```
Ack Lambda import 체인:
  slack_bolt, boto3, pydantic, src.controller.*, src.domain.common.*
  → AI SDK (openai-agents, mcp) 미사용

Worker Lambda import 체인:
  + src.domain.feat.executor
      → from agents import Agent        ← openai-agents
      → from src.agent.mcp import ...   ← mcp
```

**패키지 크기 측정:**

```bash
전체 패키지 (requirements-deploy.txt): 90MB
Ack 전용  (requirements-ack.txt):      11MB  → 87% 감소

주요 제거 대상:
  openai:       13MB
  agents:        4MB
  cryptography: 9.8MB  (openai 의존성)
  mcp:           1.8MB
```

**해결:**

```
requirements-ack.txt    requirements-deploy.txt (Worker용)
  slack-bolt              slack-bolt
  python-dotenv           openai-agents
  aiohttp                 mcp
                          python-dotenv
                          aiohttp
```

deploy.yml을 수정해 Ack / Worker 패키지를 별도 빌드 후 각 Lambda에 독립 배포.

커밋: `852201b`

---

### Step 3 — EventBridge Keep-warm (미완료)

5분 간격 ping으로 cold start 빈도를 낮춘다. Terraform 리소스 추가 필요.

```hcl
resource "aws_cloudwatch_event_rule" "keep_warm" {
  name                = "barlow-ack-keep-warm"
  schedule_expression = "rate(5 minutes)"
}
resource "aws_cloudwatch_event_target" "keep_warm" {
  rule      = aws_cloudwatch_event_rule.keep_warm.name
  target_id = "AckLambdaKeepWarm"
  arn       = aws_lambda_function.ack.arn
}
```

비용: 월 8,640회 ping → Lambda 무료 티어 내 $0

---

## After 측정 (진행 중)

Step 1, 2 배포 완료. 측정 대기.

| 측정 항목 | Before | After 목표 | After 실측 |
|---|---|---|---|
| Init Duration | 908ms | < 400ms | 측정 중 |
| Cold start 총합 | 1,558ms | < 700ms | 측정 중 |
| Slack 경험 latency (cold) | ~1,708ms | < 850ms | 측정 중 |
| 패키지 크기 | 90MB | — | 11MB ✓ |

---

## 측정 방법

**CloudWatch Logs Insights:**

```
fields @timestamp, @duration, @initDuration
| filter @type = "REPORT"
| stats
    count()                        as total,
    sum(ispresent(@initDuration))  as cold_count,
    avg(@initDuration)             as avg_init_ms,
    avg(@duration)                 as avg_handler_ms
```

**절차:**
1. Lambda cold 상태 확보 (15분 방치 or 배포 직후)
2. Slack `/feat` 커맨드 실행
3. CloudWatch REPORT 로그 확인 → Init Duration / Handler Duration 기록
4. Step 3 완료 후 동일 절차 반복
