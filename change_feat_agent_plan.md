# Feat Agent Workflow 변경 계획

## 개요

`/feat` 파이프라인에 BC 판단 단계를 추가한다. 기존에는 BC 탐색(RELEVANT_BC_FINDER) 직후 바로 이슈 초안을 생성했으나, 변경 후에는 BC 탐색 → BC 판단 제시 → 사용자 수락/거부 → 이슈 초안 생성 순으로 두 단계의 사용자 인터랙션이 존재한다.

---

## 1. 워크플로우 다이어그램

### 현재 흐름

```
/feat 슬래시 커맨드
        │
        ▼
  [Modal 제출]
        │  pipeline_start (SQS)
        ▼
RELEVANT_BC_FINDER
        │ bc_finder_output
        ▼
FEAT_ISSUE_GEN
        │ FeatTemplate
        ▼
Slack: 초안 + [수락 | 재요청 | 드롭후재탐색]
        │
    ┌───┴───────────────┐
  accept             reject / drop_restart
    │                    │
  GitHub 이슈 생성    FEAT_REISSUE_GEN
                         │
                      Slack: 새 초안 + 버튼
```

### 변경 후 흐름 (feat only)

```
/feat 슬래시 커맨드
        │
        ▼
  [Modal 제출]
        │  pipeline_start (SQS)
        ▼
RELEVANT_BC_FINDER
        │ bc_finder_output (Candidates JSON)
        ▼
BC_DECISION_MAKER
        │ BcDecision JSON
        ▼
Slack: BC 판단 결과 + [BC 수락 | BC 거부]
        │
    ┌───┴─────────────────────────────────┐
 bc_accept                           bc_reject
  (SQS)                               (SQS, 피드백 포함 가능)
    │                                    │
FEAT_ISSUE_GEN                   RELEVANT_BC_FINDER (재탐색)
  (bc_decision_output 기반)               │
    │                             BC_DECISION_MAKER
    ▼                                    │
Slack: 이슈 초안 + [수락 | 재요청 | 드롭후재탐색]
    │
┌───┴───────────────┐
accept          reject / drop_restart
    │                │
GitHub 이슈 생성   FEAT_REISSUE_GEN
                     │
                  Slack: 새 초안 + 버튼
```

---

## 2. SQS 메시지 타입

### 기존 (변경 없음)

| type | 설명 |
|------|------|
| `pipeline_start` | 슬래시 커맨드 Modal 제출 → 탐색 시작 |
| `accept` | 이슈 초안 수락 → GitHub 이슈 생성 |
| `reject` | 이슈 초안 재요청 → reissue_gen |
| `drop_restart` | 항목 드롭 후 재탐색 |

### 신규 (feat 전용)

| type | 발생 시점 | 주요 필드 |
|------|-----------|-----------|
| `bc_accept` | 사용자가 BC 판단 수락 버튼 클릭 | `message_ts`, `user_id`, `channel_id`, `dedup_id` |
| `bc_reject` | 사용자가 BC 거부 Modal 제출 | `message_ts`, `user_id`, `channel_id`, `feedback`(optional), `dedup_id` |

```json
// bc_accept
{
  "type": "bc_accept",
  "message_ts": "1234567890.123456",
  "user_id": "U...",
  "channel_id": "C...",
  "dedup_id": "<action_ts>"
}

// bc_reject
{
  "type": "bc_reject",
  "message_ts": "1234567890.123456",
  "user_id": "U...",
  "channel_id": "C...",
  "feedback": "결제 도메인보다는 주문 도메인에 가까운 것 같아요",
  "dedup_id": "<view_id>"
}
```

---

## 3. PendingRecord 변경사항

### Phase 개념 도입

| phase | 의미 | 저장 시점 |
|-------|------|-----------|
| `bc_pending` | BC 판단 결과 제시, 사용자 응답 대기 중 | BC_DECISION_MAKER 완료 후 |
| `issue_pending` | 이슈 초안 제시, 사용자 응답 대기 중 | FEAT_ISSUE_GEN 완료 후 |

refactor, fix는 기존과 동일하게 `issue_pending` phase만 사용.

### 필드 변경

```python
@dataclass
class PendingRecord:
    pk: str                              # Slack message_ts
    subcommand: str                      # "feat" | "refactor" | "fix"
    user_id: str
    channel_id: str
    user_message: str

    bc_finder_output: str                # RELEVANT_BC_FINDER 출력 (재사용)
    bc_decision_output: str | None       # BC_DECISION_MAKER 출력 (feat only, bc_pending 단계에서 None)
    typed_output: BaseIssueTemplate | None  # 이슈 초안 (bc_pending 단계에서 None)

    phase: Literal["bc_pending", "issue_pending"]  # 신규

    ttl: int
```

- `from_item()`에서 `phase` 필드 없을 경우 기본값 `"issue_pending"` (기존 레코드 하위 호환)
- `typed_output`을 Optional로 변경

---

## 4. BC_DECISION_MAKER 에이전트

### 현재 상태

`agent_info.py`에 `BC_DECISION_MAKER` AgentInfo와 `BcDecision` 출력 스키마는 이미 정의되어 있으나 `output_format` 필드가 누락된 버그가 있음.

### 수정

```python
BC_DECISION_MAKER = AgentInfo(
    name="bc_decision_maker",
    sys_prompt="""...""",          # 기존 유지
    output_format=BcDecision,     # 추가
)
```

### 입출력 스펙

**입력 프롬프트**
```
[User Request]
{user_message}

[BC Finder Candidates]
{bc_finder_output}
```

**출력 (BcDecision — 이미 정의됨)**
```python
class BcDecision(BaseModel):
    class SelectedContext(BaseModel):
        name: str
        type: Literal["existing", "proposed"]
        confidence: float
        reason: str

    decision: Literal["reuse_existing", "propose_new"]
    new_bc_needed: bool
    selected_contexts: list[SelectedContext]
    primary_context: str
    supporting_contexts: list[str]
    mapping_summary: str
    rationale: str
    validation_points: list[str]
    issue_focus: str
```

**MCP 도구**: `GitHubMCPFactory.readProject()` (DOMAIN_ENCYCLOPEDIA.md 참조 필요)

---

## 5. 새 서비스 함수

| 파일 | 함수 | 역할 |
|------|------|------|
| `src/services/bc_decision_maker.py` (신규) | `run_bc_decision_maker(user_message, bc_finder_output) -> tuple[str, AgentUsage]` | BC_DECISION_MAKER 실행, BcDecision JSON + usage 반환 |
| `src/services/issue_generator.py` (수정) | `run_issue_generator(subcommand, bc_finder_output, bc_decision_output=None)` | feat 시 bc_decision_output을 프롬프트에 추가 |

---

## 6. Slack 인터랙션 변경

### 신규: BC 판단 결과 메시지

```
<@user_id>

*BC 판단 결과*

*결정*: 기존 BC 재사용
*주요 컨텍스트*: OrderContext
*근거*: ...mapping_summary...

*선택된 컨텍스트*
• OrderContext (existing, 0.92) — 결제 흐름의 핵심 집계 루트
• PaymentContext (existing, 0.75) — 지원 컨텍스트

*검증 포인트*
• 포인트 1
• 포인트 2

[BC 수락] [BC 거부]
```

**신규 빌더 함수**:
- `build_bc_decision_blocks(user, bc_decision_json, usage_text) -> list[dict]`
- `build_bc_reject_modal(message_ts, channel_id, user_id) -> dict`

**신규 액션 핸들러**:
- `action_id: "bc_accept"` → `bc_accept` SQS 전송
- `action_id: "bc_reject"` → BC 거부 Modal 오픈
- `callback_id: "bc_reject_submit"` → `bc_reject` SQS 전송

---

## 7. 변경 파일 목록

| 파일 | 변경 내용 |
|------|-----------|
| `src/agent/agent_info.py` | `BC_DECISION_MAKER` output_format 버그 수정 |
| `src/agent/agent_factory.py` | `bc_decision_maker()` 메서드 추가 |
| `src/domain/pending.py` | `phase`, `bc_decision_output` 필드 추가, `typed_output` Optional화 |
| `src/services/bc_decision_maker.py` | 신규 작성 |
| `src/services/issue_generator.py` | feat 시 `bc_decision_output` 프롬프트 포함 |
| `src/controller/_reply.py` | BC 판단 블록 빌더, BC 거부 Modal 추가 |
| `src/controller/handler/slash.py` | `bc_accept`, `bc_reject`, `bc_reject_submit` 핸들러 추가 |
| `src/lambda_worker.py` | `_handle_pipeline_start` feat 분기, `_handle_bc_accept`, `_handle_bc_reject` 추가 |

---

## 8. bc_reject 재탐색 전략

피드백을 `user_message`에 append하여 재탐색. 기존 `bc_finder_output` 폐기하고 재실행.

```python
enriched_message = (
    f"{record.user_message}\n\n[사용자 피드백]\n{feedback}"
    if feedback else record.user_message
)
bc_finder_output, _ = await run_read_planner(enriched_message)
bc_decision_output, usage = await run_bc_decision_maker(enriched_message, bc_finder_output)
```

---

## 9. 단계별 구현 순서

| Step | 대상 | 내용 |
|------|------|------|
| 1 | `src/domain/pending.py` | phase, bc_decision_output 필드 추가, Optional typed_output |
| 2 | `src/agent/agent_info.py` | BC_DECISION_MAKER output_format 버그 수정 |
| 3 | `src/agent/agent_factory.py` | bc_decision_maker() 추가 |
| 4 | `src/services/bc_decision_maker.py` | 신규 서비스 작성 |
| 5 | `src/services/issue_generator.py` | feat bc_decision_output 인자 추가 |
| 6 | `src/controller/_reply.py` | BC 판단 블록/Modal 빌더 추가 |
| 7 | `src/controller/handler/slash.py` | bc_accept/reject 핸들러 등록 |
| 8 | `src/lambda_worker.py` | 파이프라인 핸들러 수정/추가 |
