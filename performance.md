# Ack Lambda 성능 분석 및 최적화

---

## 측정 환경

- Lambda: `barlow-slack-ack` (arm64 / Graviton, 256MB)
- 트리거: Slack `/feat` 슬래시 커맨드 → Lambda Function URL
- 측정 방법: CloudWatch REPORT 로그

---

## 실측 수치 (기준선 — 2025-03-29)

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

Init Duration 편차: ±10ms → **패키지 크기 기반, 재현 가능**
Handler cold 오버헤드: +334ms → boto3 첫 TCP connection 비용

**cold/warm Handler 차이: +334ms**
→ cold start 시 boto3 첫 TCP connection(SQS/DynamoDB) 비용 포함.
warm start에서는 connection이 재사용되어 사라진다.

---

## Slack이 경험하는 실제 latency

```
Slack → api.slack.com → Function URL → Lambda → 응답

warm: 316ms + 네트워크 ~150ms  = ~466ms    ✓ 안전
cold: 1558ms + 네트워크 ~150ms = ~1708ms  △ margin 1.3초
```

현재는 3초 이내이나 Slack API 응답(views_open)이 300ms 이상 지연되면
cold start 총합이 2초를 초과할 수 있다.

---

## 문제 구조

```
월 30회 호출 → 호출 간격이 길다 → 대부분 cold start
cold start (~1,708ms) → Slack 3초 초과 위험 → timeout → retry → dedup 필요
```

dedup 레이어(pending-action, active-session)가 존재하는 근본 원인 중 하나가
cold start로 인한 Slack retry다.

---

## 구조적 결합 문제

Lambda 진입점이 Slack Bolt에 종속되어 있다.

```python
# lambda_ack.py — 현재
def handler(event: dict, context) -> dict:
    return asyncio.run(_dispatch(event))  # 모든 이벤트가 Bolt를 통과
```

- EventBridge keep-warm ping을 보내도 Bolt 서명 검증에서 차단됨
- k6 측정 요청이 Slack API(views_open) 호출을 유발해 latency 오염
- 진입점에서 Slack 이벤트와 운영 이벤트를 구분하지 못함

---

## Handler Duration 분해 추정

```
cold handler 650ms (평균):
  views_open (Slack API):        ~200ms
  SQS send (첫 TCP connection):  ~300ms   ← warm 대비 ~3배
  routing / ack:                 ~150ms

warm handler 316ms (평균):
  views_open (Slack API):        ~180ms
  SQS send (connection 재사용):  ~100ms
  routing / ack:                  ~36ms
```

---

## 최적화 목표

| 항목 | 현재 | 목표 | 수단 |
|---|---|---|---|
| Init Duration | 918ms | < 400ms | lazy import |
| Cold start 빈도 | 대부분 | 낮춤 | EventBridge keep-warm |
| Lambda 진입점 결합 | Bolt 종속 | 이벤트 유형 분기 | handler 분리 |

---

## 구현 계획

### Step 1 — Lambda 진입점 분리

Slack 이벤트와 운영 이벤트를 진입점에서 분기한다.

```python
def handler(event: dict, context) -> dict:
    # EventBridge keep-warm ping
    if event.get("source") == "aws.events":
        logger.info("keep-warm ping")
        return {"statusCode": 200, "body": "warm"}

    # Slack HTTP 이벤트만 Bolt로 디스패치
    return asyncio.run(_dispatch(event))
```

효과:
- keep-warm ping이 Bolt 우회 → Lambda는 warm 상태 유지
- k6 헬스체크 엔드포인트도 같은 방식으로 추가 가능
- Slack 결합을 진입점 바깥으로 밀어냄

### Step 2 — Lazy Import

모듈 레벨에서 발생하는 Init Duration 918ms의 주요 원인을 분석하고 지연 로딩으로 줄인다.

```python
# 현재 — 모듈 import 시 즉시 실행
from slack_bolt.async_app import AsyncApp
slash.configure(
    workflow_repo=DynamoWorkflowInstanceStore(),  # boto3 클라이언트 생성
    ...
)
_app = create_app()
register(_app)

# 목표 — 첫 Slack 이벤트 도착 시 초기화 (keep-warm ping 이후)
_app: AsyncApp | None = None

def _get_app() -> AsyncApp:
    global _app
    if _app is None:
        _app = _initialize()
    return _app
```

효과:
- keep-warm ping은 Python 런타임 + 모듈 import만 실행하고 반환
- 실제 Slack 이벤트 첫 처리 시 초기화 → 이후 warm에서 재사용
- Init Duration 목표: 918ms → 400ms 이하

### Step 3 — EventBridge Scheduled Ping

5분 간격으로 Lambda를 깨운다.

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

효과:
- 5분 이내 재호출이면 항상 warm 상태
- 월 30회 실사용 기준 ping 비용: ~8,640회/월 → Lambda 무료 티어 내 $0
- cold start 빈도: 거의 0% (Lambda 최대 idle 시간 > 5분이면 cold)

---

## Before / After 비교 기준

| 측정 항목 | Before | After 목표 |
|---|---|---|
| Init Duration | 918ms | < 400ms |
| Cold start 총합 | 1,558ms | < 600ms |
| Slack 경험 latency (cold) | ~1,708ms | < 750ms |
| Cold start 빈도 | 높음 (~100%) | < 5% |

---

## 측정 방법

```
[Before 기준선]
1. Lambda cold 상태 확보 (15분 방치 or 배포 직후)
2. k6 run k6/ack_lambda.js → HTTP 응답 시간 분포 기록
3. CloudWatch Logs Insights → Init Duration / Handler Duration 기록

[After 검증]
4. Step 1~3 구현 후 배포
5. 동일 절차 반복
6. 수치 비교
```

CloudWatch Logs Insights 쿼리:
```
fields @timestamp, @duration, @initDuration
| filter @type = "REPORT"
| stats
    count()                        as total,
    sum(ispresent(@initDuration))  as cold_count,
    avg(@initDuration)             as avg_init_ms,
    avg(@duration)                 as avg_handler_ms
```


문제: 월 30회 희소 트래픽 → 대부분 cold start → Slack timeout 위험
해결 1: EventBridge 5분 ping → cold start 빈도 0%에 가깝게
해결 2: Lazy import → cold start 발생해도 908ms → ~400ms
결과: Slack 경험 latency 1,708ms → ~600ms