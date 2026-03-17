# 테스트 계획 (test-plan.md)

---

## 목표

| 구분 | 범위 | 외부 연동 |
|------|------|-----------|
| **Unit** | 도메인 모델, controller 빌더, service 파이프라인 | 없음 (모두 mock) |
| **Integration** | Lambda 핸들러 — 요청 단위 전체 흐름 | SQS·DynamoDB·Slack·Agent mock |

Unit은 함수/클래스 레벨 정확성을 보장한다.
Integration은 Lambda 진입점부터 외부 호출 직전까지 요청 흐름 전체를 검증한다.

---

## 기술 스택

```
pytest
pytest-asyncio          # async 테스트
moto[dynamodb]          # DynamoDB local mock
unittest.mock           # boto3, Slack SDK, AgentFactory mock
slack_bolt              # BoltRequest — Ack Lambda 핸들러 테스트
```

`pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

---

## 디렉토리 구조

```
tests/
├── conftest.py                      # 공통 fixture
├── unit/
│   ├── domain/
│   │   ├── test_issue_templates.py
│   │   └── test_pending.py
│   ├── controller/
│   │   ├── test_issue_drop.py
│   │   ├── test_reply.py
│   │   └── test_modal_templates.py
│   ├── services/
│   │   ├── test_read_planner.py
│   │   ├── test_issue_generator.py
│   │   └── test_re_issue_generator.py
│   └── agent/
│       └── test_agent_factory.py
└── integration/
    ├── test_lambda_ack.py           # Ack Lambda — Slack 이벤트 → SQS/views_open
    └── test_lambda_worker.py        # Worker Lambda — SQS 이벤트 → 서비스 → Slack
```

---

## Phase 1 — 환경 설정

### 목표
테스트 실행 가능한 기반 환경 구성.

### 설치

```bash
pip install pytest pytest-asyncio moto boto3
```

### `tests/conftest.py`

```python
import pytest
from src.domain.issue_templates import FeatTemplate, RefactorTemplate, FixTemplate

@pytest.fixture
def feat_template() -> FeatTemplate:
    return FeatTemplate(
        issue_title="[FEAT] 즐겨찾기",
        about="자주 방문하는 페이지를 저장한다.",
        new_features=["즐겨찾기 추가", "즐겨찾기 조회", "즐겨찾기 삭제"],
        domain_rules=["로그인 사용자만 가능"],
        domain_constraints=["REST API 방식"],
    )

@pytest.fixture
def refactor_template() -> RefactorTemplate:
    Goal = RefactorTemplate._Goal
    return RefactorTemplate(
        issue_title="[REFACTOR] SessionManager 분리",
        about="단일 책임 원칙 위반 해소.",
        goals=[
            Goal(as_is=["SessionManager가 저장소 직접 참조"], to_be=["IStore 인터페이스 주입"]),
            Goal(as_is=["InMemoryStore 하드코딩"], to_be=["DI로 교체 가능"]),
        ],
        domain_rules=["기존 API 시그니처 유지"],
        domain_constraints=["Python 3.12+"],
    )

@pytest.fixture
def fix_template() -> FixTemplate:
    Problem = FixTemplate._Problem
    Step = FixTemplate._ImplementationStep
    return FixTemplate(
        issue_title="[FIX] 로그인 시 NPE",
        about="인증 토큰 누락 시 NullPointerException 발생.",
        problems=[Problem(issue="토큰 null 미검증", suggestion="Optional 체크 추가")],
        implementation=[Step(step=1, todo="토큰 null 검증 로직 추가")],
        domain_rules=["보안 정책 유지"],
        domain_constraints=["기존 인터페이스 변경 불가"],
    )
```

---

## Phase 2 — 도메인 Unit Test

### 목표
순수 데이터 모델의 정확성 보장. 의존성 없음.

### `tests/unit/domain/test_issue_templates.py`

```python
from src.domain.issue_templates import Label, FeatTemplate

def test_label_values():
    assert Label.FEAT.value == "feat"
    assert Label.REFACTOR.value == "refactor"
    assert Label.FIX.value == "fix"

def test_feat_template_label(feat_template):
    assert feat_template.label == Label.FEAT

def test_refactor_template_label(refactor_template):
    assert refactor_template.label == Label.REFACTOR

def test_fix_template_label(fix_template):
    assert fix_template.label == Label.FIX
```

### `tests/unit/domain/test_pending.py`

```python
import pytest
from src.domain.pending import PendingRecord

@pytest.fixture
def pending_record(feat_template) -> PendingRecord:
    return PendingRecord(
        pk="1234567890.123456",
        subcommand="feat",
        user_id="U123",
        channel_id="C456",
        user_message="[feat] 즐겨찾기",
        inspector_output='{"request_summary": "즐겨찾기 추가"}',
        typed_output=feat_template,
    )

# to_item → from_item 왕복
def test_pending_record_roundtrip(pending_record):
    restored = PendingRecord.from_item(pending_record.to_item())
    assert restored.pk == pending_record.pk
    assert restored.subcommand == pending_record.subcommand
    assert restored.typed_output.issue_title == pending_record.typed_output.issue_title
    assert restored.typed_output.new_features == pending_record.typed_output.new_features

# 역직렬화 시 올바른 타입으로 복원
def test_pending_record_restores_correct_template_type(pending_record):
    from src.domain.issue_templates import FeatTemplate
    restored = PendingRecord.from_item(pending_record.to_item())
    assert isinstance(restored.typed_output, FeatTemplate)

# refactor/fix 타입 복원
def test_pending_record_refactor_roundtrip(refactor_template):
    from src.domain.issue_templates import RefactorTemplate
    record = PendingRecord(
        pk="ts", subcommand="refactor",
        user_id="U1", channel_id="C1",
        user_message="msg", inspector_output="{}",
        typed_output=refactor_template,
    )
    restored = PendingRecord.from_item(record.to_item())
    assert isinstance(restored.typed_output, RefactorTemplate)
    assert len(restored.typed_output.goals) == 2

# TTL 기본값 설정
def test_pending_record_default_ttl_is_positive(pending_record):
    assert pending_record.ttl > 0

# to_item 필수 키 포함
def test_pending_record_to_item_has_required_keys(pending_record):
    item = pending_record.to_item()
    for key in ["pk", "subcommand", "user_id", "channel_id", "user_message", "inspector_output", "typed_output", "ttl"]:
        assert key in item
```

---

## Phase 3 — Controller Unit Test

### 목표
드롭 로직, Block Kit 빌더, Modal 파싱/직렬화 검증.

### `tests/unit/controller/test_issue_drop.py`

```python
from src.controller.issue_drop import droppable_items, drop_items, DroppableItem

# ── droppable_items ──────────────────────────────────────────────────────────

def test_droppable_items_ids_unique(feat_template):
    ids = [i.id for i in droppable_items(feat_template)]
    assert len(ids) == len(set(ids))

def test_droppable_items_covers_all_sections(feat_template):
    sections = {i.section for i in droppable_items(feat_template)}
    assert {"신규 기능", "도메인 규칙", "기술 제약"} <= sections

def test_droppable_items_id_format(feat_template):
    items = droppable_items(feat_template)
    feat_ids = [i.id for i in items if i.section == "신규 기능"]
    assert feat_ids == ["new_features::0", "new_features::1", "new_features::2"]

def test_droppable_items_refactor_contains_goals(refactor_template):
    items = droppable_items(refactor_template)
    goal_items = [i for i in items if i.section.startswith("목표")]
    assert len(goal_items) == 2

def test_droppable_items_fix_contains_problems(fix_template):
    items = droppable_items(fix_template)
    assert any(i.section == "문제" for i in items)
    assert any(i.section == "구현 단계" for i in items)

# ── drop_items ───────────────────────────────────────────────────────────────

def test_drop_items_removes_correct_item(feat_template):
    result = drop_items(feat_template, {"new_features::1"})
    assert result.new_features == ["즐겨찾기 추가", "즐겨찾기 삭제"]

def test_drop_items_empty_set_returns_all(feat_template):
    result = drop_items(feat_template, set())
    assert result.new_features == feat_template.new_features

def test_drop_items_removes_all(feat_template):
    ids = {"new_features::0", "new_features::1", "new_features::2"}
    result = drop_items(feat_template, ids)
    assert result.new_features == []

def test_drop_items_removes_domain_rule(feat_template):
    result = drop_items(feat_template, {"domain_rules::0"})
    assert result.domain_rules == []

def test_drop_items_refactor_removes_goal(refactor_template):
    result = drop_items(refactor_template, {"goals::0"})
    assert len(result.goals) == 1
    assert result.goals[0].as_is == ["InMemoryStore 하드코딩"]

def test_drop_items_fix_removes_problem(fix_template):
    result = drop_items(fix_template, {"problems::0"})
    assert result.problems == []

def test_drop_items_fix_removes_implementation_step(fix_template):
    result = drop_items(fix_template, {"implementation::0"})
    assert result.implementation == []

# drop 후 droppable_items id 재색인 — 인덱스는 드롭 후 재계산됨
def test_drop_items_reindexed_after_drop(feat_template):
    result = drop_items(feat_template, {"new_features::0"})
    # "즐겨찾기 조회"가 index 0으로 재색인
    items = droppable_items(result)
    feat_items = [i for i in items if i.section == "신규 기능"]
    assert feat_items[0].id == "new_features::0"
    assert feat_items[0].text == "즐겨찾기 조회"
```

### `tests/unit/controller/test_reply.py`

```python
import json
from src.controller._reply import (
    build_issue_blocks, build_reject_modal, build_drop_modal
)
from src.controller.issue_drop import DroppableItem

# ── build_issue_blocks ───────────────────────────────────────────────────────

def test_build_issue_blocks_has_three_buttons(feat_template):
    blocks = build_issue_blocks("U123", feat_template, "")
    action = next(b for b in blocks if b["type"] == "actions")
    ids = [e["action_id"] for e in action["elements"]]
    assert ids == ["issue_accept", "issue_reject", "issue_drop"]

def test_build_issue_blocks_no_context_when_no_usage(feat_template):
    blocks = build_issue_blocks("U123", feat_template, "")
    assert not any(b["type"] == "context" for b in blocks)

def test_build_issue_blocks_has_context_when_usage_present(feat_template):
    blocks = build_issue_blocks("U123", feat_template, "in=100 out=200")
    assert any(b["type"] == "context" for b in blocks)

def test_build_issue_blocks_splits_long_text():
    from src.domain.issue_templates import FeatTemplate
    t = FeatTemplate(
        issue_title="T", about="A",
        new_features=["x" * 3000],
        domain_rules=[], domain_constraints=[],
    )
    sections = [b for b in build_issue_blocks(None, t, "") if b["type"] == "section"]
    assert len(sections) >= 2

def test_build_issue_blocks_mention_when_user_provided(feat_template):
    blocks = build_issue_blocks("U123", feat_template, "")
    section_texts = [b["text"]["text"] for b in blocks if b["type"] == "section"]
    assert any("<@U123>" in t for t in section_texts)

# ── build_reject_modal ───────────────────────────────────────────────────────

def test_build_reject_modal_callback_id():
    modal = build_reject_modal("ts1", "C1", "U1")
    assert modal["callback_id"] == "reject_submit"

def test_build_reject_modal_private_metadata():
    modal = build_reject_modal("ts1", "C1", "U1")
    meta = json.loads(modal["private_metadata"])
    assert meta == {"message_ts": "ts1", "channel_id": "C1", "user_id": "U1"}

def test_build_reject_modal_has_text_input():
    modal = build_reject_modal("ts1", "C1", "U1")
    assert modal["blocks"][0]["element"]["type"] == "plain_text_input"

# ── build_drop_modal ─────────────────────────────────────────────────────────

def test_build_drop_modal_callback_id():
    modal = build_drop_modal("ts1", "C1", "U1", [])
    assert modal["callback_id"] == "drop_submit"

def test_build_drop_modal_option_count():
    items = [
        DroppableItem(id="f::0", section="신규 기능", text="A"),
        DroppableItem(id="f::1", section="신규 기능", text="B"),
    ]
    modal = build_drop_modal("ts1", "C1", "U1", items)
    options = modal["blocks"][0]["element"]["options"]
    assert len(options) == 2
    assert options[0]["value"] == "f::0"

def test_build_drop_modal_empty_items():
    modal = build_drop_modal("ts1", "C1", "U1", [])
    assert modal["blocks"][0]["element"]["options"] == []
```

### `tests/unit/controller/test_modal_templates.py`

```python
from src.controller.modal_templates.feat_modal_input import FeatModalInput
from src.controller.modal_templates.refactor_modal_input import RefactorModalInput
from src.controller.modal_templates.fix_modal_input import FixModalInput
from src.controller.modal_templates.modal_templates import _parse_bullets

def _feat_values(**overrides) -> dict:
    base = {
        "feature_name":        {"input": {"value": "즐겨찾기"}},
        "background":          {"input": {"value": "자주 쓰는 페이지"}},
        "features":            {"input": {"value": "- 추가\n- 조회"}},
        "constraints":         {"input": {"value": "로그인 필요"}},
        "design_requirements": {"input": {"value": None}},
    }
    return {**base, **overrides}

# ── FeatModalInput ────────────────────────────────────────────────────────────

def test_feat_from_view_parses_correctly():
    modal = FeatModalInput.from_view(_feat_values())
    assert modal.feature_name == "즐겨찾기"
    assert modal.background == "자주 쓰는 페이지"
    assert modal.design_requirements == ""

def test_feat_to_prompt_header():
    assert FeatModalInput.from_view(_feat_values()).to_prompt().startswith("[feat] 즐겨찾기")

def test_feat_to_prompt_excludes_empty_design():
    assert "설계 요구사항" not in FeatModalInput.from_view(_feat_values()).to_prompt()

def test_feat_to_prompt_includes_design_when_present():
    values = _feat_values(**{"design_requirements": {"input": {"value": "GET /api/v1"}}})
    assert "설계 요구사항" in FeatModalInput.from_view(values).to_prompt()

# ── RefactorModalInput ────────────────────────────────────────────────────────

def test_refactor_to_prompt_header():
    values = {
        "target_name":  {"input": {"value": "SessionManager"}},
        "background":   {"input": {"value": "단일 책임 위반"}},
        "as_is":        {"input": {"value": "직접 참조"}},
        "to_be":        {"input": {"value": "인터페이스 주입"}},
        "constraints":  {"input": {"value": None}},
    }
    assert RefactorModalInput.from_view(values).to_prompt().startswith("[refactor] SessionManager")

# ── FixModalInput ─────────────────────────────────────────────────────────────

def test_fix_to_prompt_header():
    values = {
        "bug_title":     {"input": {"value": "로그인 NPE"}},
        "symptom":       {"input": {"value": "null 참조"}},
        "reproduction":  {"input": {"value": "로그인 시"}},
        "expected":      {"input": {"value": "정상 처리"}},
        "related_areas": {"input": {"value": None}},
    }
    assert FixModalInput.from_view(values).to_prompt().startswith("[fix] 로그인 NPE")

# ── _parse_bullets ────────────────────────────────────────────────────────────

def test_parse_bullets_strips_dash():
    assert _parse_bullets("- A\n- B") == ["A", "B"]

def test_parse_bullets_strips_bullet():
    assert _parse_bullets("• A\n• B") == ["A", "B"]

def test_parse_bullets_ignores_empty_lines():
    assert _parse_bullets("A\n\nB") == ["A", "B"]

def test_parse_bullets_plain_text():
    assert _parse_bullets("A\nB\nC") == ["A", "B", "C"]
```

---

## Phase 4 — Service Unit Test

### 목표
AgentFactory를 mock해 파이프라인 제어 흐름과 usage 누적 검증.

### 공통 fixture (`conftest.py` 추가)

```python
from unittest.mock import AsyncMock
from src.agent.base import AgentResult
from src.agent.usage import AgentUsage

def make_agent_result(output: str, typed_output=None, in_tokens=10, out_tokens=5):
    return AgentResult(
        output=output,
        usage=AgentUsage(in_tokens, out_tokens),
        typed_output=typed_output,
    )
```

### `tests/unit/services/test_read_planner.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.agent.agent_factory import AgentFactory
from src.services.read_planner import run_read_planner

@pytest.mark.asyncio
async def test_run_read_planner_calls_planner_then_inspector(make_agent_result):
    mock_planner = AsyncMock()
    mock_planner.run.return_value = make_agent_result("plan_out")
    mock_inspector = AsyncMock()
    mock_inspector.run.return_value = make_agent_result("inspector_out")

    with patch.object(AgentFactory, "read_planner", return_value=mock_planner), \
         patch.object(AgentFactory, "inspector", return_value=mock_inspector):
        output, _ = await run_read_planner("user msg")

    mock_planner.run.assert_awaited_once_with("user msg")
    mock_inspector.run.assert_awaited_once_with("plan_out")  # planner 출력이 inspector 입력
    assert output == "inspector_out"

@pytest.mark.asyncio
async def test_run_read_planner_accumulates_usage(make_agent_result):
    mock_planner = AsyncMock()
    mock_planner.run.return_value = make_agent_result("", in_tokens=10, out_tokens=5)
    mock_inspector = AsyncMock()
    mock_inspector.run.return_value = make_agent_result("", in_tokens=20, out_tokens=8)

    with patch.object(AgentFactory, "read_planner", return_value=mock_planner), \
         patch.object(AgentFactory, "inspector", return_value=mock_inspector):
        _, usage = await run_read_planner("msg")

    assert usage.input_tokens == 30
    assert usage.output_tokens == 13
```

### `tests/unit/services/test_issue_generator.py`

```python
@pytest.mark.asyncio
async def test_run_issue_generator_returns_typed_output(feat_template, make_agent_result):
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result("", typed_output=feat_template)

    with patch.object(AgentFactory, "issue_gen", return_value=mock_agent):
        template, usage = await run_issue_generator("feat", "inspector_out")

    mock_agent.run.assert_awaited_once_with("inspector_out")
    assert template is feat_template

@pytest.mark.asyncio
async def test_run_issue_generator_passes_correct_subcommand(feat_template, make_agent_result):
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result("", typed_output=feat_template)

    with patch.object(AgentFactory, "issue_gen", return_value=mock_agent) as mock_factory:
        await run_issue_generator("refactor", "out")

    mock_factory.assert_called_once_with("refactor")
```

### `tests/unit/services/test_re_issue_generator.py`

```python
@pytest.mark.asyncio
async def test_prompt_contains_required_sections(feat_template, make_agent_result):
    from src.domain.pending import PendingRecord
    record = PendingRecord(pk="ts", subcommand="feat", user_id="U1", channel_id="C1",
                           user_message="msg", inspector_output='{"summary":"..."}',
                           typed_output=feat_template)
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result("", typed_output=feat_template)

    with patch.object(AgentFactory, "reissue_gen", return_value=mock_agent):
        await run_re_issue_generator(record)

    prompt = mock_agent.run.call_args[0][0]
    assert "[Inspector Context]" in prompt
    assert "[Current Issue Draft]" in prompt

@pytest.mark.asyncio
async def test_prompt_includes_additional_requirements(feat_template, make_agent_result):
    from src.domain.pending import PendingRecord
    record = PendingRecord(pk="ts", subcommand="feat", user_id="U1", channel_id="C1",
                           user_message="msg", inspector_output="{}", typed_output=feat_template)
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result("", typed_output=feat_template)

    with patch.object(AgentFactory, "reissue_gen", return_value=mock_agent):
        await run_re_issue_generator(record, additional_requirements="성능 개선 추가")

    assert "Additional requirements: 성능 개선 추가" in mock_agent.run.call_args[0][0]

@pytest.mark.asyncio
async def test_no_additional_requirements_section_when_none(feat_template, make_agent_result):
    from src.domain.pending import PendingRecord
    record = PendingRecord(pk="ts", subcommand="feat", user_id="U1", channel_id="C1",
                           user_message="msg", inspector_output="{}", typed_output=feat_template)
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result("", typed_output=feat_template)

    with patch.object(AgentFactory, "reissue_gen", return_value=mock_agent):
        await run_re_issue_generator(record, additional_requirements=None)

    assert "Additional requirements" not in mock_agent.run.call_args[0][0]
```

---

## Phase 5 — Agent Unit Test

### `tests/unit/agent/test_agent_factory.py`

```python
from unittest.mock import patch, MagicMock
import pytest
from src.agent.agent_factory import AgentFactory
from src.agent.agent_info import AvailableAgents

@patch("src.agent.agent_factory.GitHubMCPFactory.readProjectTree")
@patch("src.agent.agent_factory.GitHubMCPFactory.readProject")
@patch("src.agent.agent_factory.Agent")
def test_inspector_uses_tree_mcp(mock_agent, mock_project, mock_tree):
    AgentFactory.inspector()
    mock_tree.assert_called_once()
    mock_project.assert_not_called()

@patch("src.agent.agent_factory.GitHubMCPFactory.readProject")
@patch("src.agent.agent_factory.Agent")
@pytest.mark.parametrize("subcommand,expected", [
    ("feat",     AvailableAgents.FEAT_ISSUE_GEN),
    ("refactor", AvailableAgents.REFACTOR_ISSUE_GEN),
    ("fix",      AvailableAgents.FIX_ISSUE_GEN),
])
def test_issue_gen_selects_correct_key(mock_agent, mock_project, subcommand, expected):
    with patch.object(AgentFactory, "_build") as mock_build:
        AgentFactory.issue_gen(subcommand)
        assert mock_build.call_args[0][0] == expected

@pytest.mark.parametrize("subcommand,expected", [
    ("feat",     AvailableAgents.FEAT_REISSUE_GEN),
    ("refactor", AvailableAgents.REFACTOR_REISSUE_GEN),
    ("fix",      AvailableAgents.FIX_REISSUE_GEN),
])
def test_reissue_gen_selects_correct_key(subcommand, expected):
    with patch.object(AgentFactory, "_build") as mock_build:
        with patch("src.agent.agent_factory.GitHubMCPFactory.readProject"):
            AgentFactory.reissue_gen(subcommand)
            assert mock_build.call_args[0][0] == expected

def test_issue_gen_invalid_subcommand_raises():
    with pytest.raises(KeyError):
        AgentFactory.issue_gen("unknown")

def test_reissue_gen_invalid_subcommand_raises():
    with pytest.raises(KeyError):
        AgentFactory.reissue_gen("unknown")
```

---

## Phase 6 — Lambda Integration Test

### 목표
Lambda 진입점부터 외부 호출 직전까지 요청 흐름 전체를 end-to-end로 검증.
외부 연동(SQS, DynamoDB, Slack API, Agent)은 모두 mock.

---

### `tests/integration/test_lambda_ack.py`

Slack Bolt `AsyncApp`에 실제 이벤트 payload를 주입해 핸들러 동작 검증.

```
검증 대상:
  /feat, /refactor, /fix  →  views_open 호출
  feat_submit 등          →  SQS.send_message 호출 + payload 검증
  issue_accept            →  SQS.send_message(type="accept")
  issue_reject            →  views_open(reject modal)
  issue_drop              →  DynamoDB.get → views_open(drop modal)
  reject_submit           →  SQS.send_message(type="reject") + additional_requirements
  drop_submit             →  SQS.send_message(type="drop_restart") + dropped_ids
```

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.views_open = AsyncMock(return_value={"ok": True})
    return client

@pytest.fixture
def mock_sqs():
    with patch("src.controller.handler.slash._sqs") as mock:
        yield mock

@pytest.fixture
def mock_pending_repo(feat_template):
    from src.domain.pending import PendingRecord
    record = PendingRecord(
        pk="msg_ts_123", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", inspector_output="{}",
        typed_output=feat_template,
    )
    with patch("src.controller.handler.slash._pending_repo") as mock:
        mock.get = AsyncMock(return_value=record)
        yield mock

# /feat → views_open 호출 + FeatModalInput blocks 포함
@pytest.mark.asyncio
async def test_slash_feat_opens_modal(mock_client, mock_sqs):
    from src.controller.handler.slash import register
    from slack_bolt.async_app import AsyncApp
    app = AsyncApp(token="xoxb-test", signing_secret="secret")
    register(app)

    command = {"trigger_id": "trig1", "channel_id": "C1", "user_id": "U1", "text": ""}
    await app._process_event({"type": "slash_commands", "command": "/feat", **command})

    mock_client.views_open.assert_awaited_once()
    view = mock_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "feat_submit"

# feat_submit → SQS pipeline_start 전송
@pytest.mark.asyncio
async def test_feat_submit_puts_sqs(mock_sqs):
    from src.controller.handler.slash import handle_feat_submit  # 직접 호출 방식

    body = {"user": {"id": "U1"}, "view": {"id": "view_1", "private_metadata": '{"channel_id":"C1"}'}}
    view = {
        "id": "view_1",
        "private_metadata": '{"channel_id": "C1"}',
        "state": {"values": {
            "feature_name":        {"input": {"value": "즐겨찾기"}},
            "background":          {"input": {"value": "배경"}},
            "features":            {"input": {"value": "기능"}},
            "constraints":         {"input": {"value": "제약"}},
            "design_requirements": {"input": {"value": None}},
        }},
    }
    await handle_feat_submit(ack=AsyncMock(), body=body, view=view)

    mock_sqs.send_message.assert_called_once()
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "pipeline_start"
    assert payload["subcommand"] == "feat"
    assert payload["channel_id"] == "C1"
    assert payload["user_id"] == "U1"
    assert "[feat]" in payload["user_message"]
    assert "dedup_id" in payload

# issue_accept → SQS accept 전송
@pytest.mark.asyncio
async def test_issue_accept_puts_sqs(mock_sqs):
    from src.controller.handler.slash import handle_accept
    body = {
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
        "message": {"ts": "msg_ts_123"},
        "actions": [{"action_ts": "act_ts_1"}],
    }
    await handle_accept(ack=AsyncMock(), body=body)

    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "accept"
    assert payload["message_ts"] == "msg_ts_123"

# issue_reject → views_open(reject modal)
@pytest.mark.asyncio
async def test_issue_reject_opens_reject_modal(mock_client):
    from src.controller.handler.slash import handle_reject
    body = {
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
        "message": {"ts": "msg_ts_123"},
        "trigger_id": "trig1",
    }
    await handle_reject(ack=AsyncMock(), client=mock_client, body=body)

    view = mock_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "reject_submit"
    meta = json.loads(view["private_metadata"])
    assert meta["message_ts"] == "msg_ts_123"

# issue_drop → DynamoDB 조회 후 drop modal
@pytest.mark.asyncio
async def test_issue_drop_opens_drop_modal(mock_client, mock_pending_repo):
    from src.controller.handler.slash import handle_drop
    body = {
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
        "message": {"ts": "msg_ts_123"},
        "trigger_id": "trig1",
    }
    await handle_drop(ack=AsyncMock(), client=mock_client, body=body)

    mock_pending_repo.get.assert_awaited_once_with("msg_ts_123")
    view = mock_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "drop_submit"

# issue_drop — pending record 없으면 views_open 미호출
@pytest.mark.asyncio
async def test_issue_drop_no_record_skips_modal(mock_client):
    from src.controller.handler.slash import handle_drop
    body = {
        "user": {"id": "U1"}, "channel": {"id": "C1"},
        "message": {"ts": "missing_ts"}, "trigger_id": "trig1",
    }
    with patch("src.controller.handler.slash._pending_repo") as mock_repo:
        mock_repo.get = AsyncMock(return_value=None)
        await handle_drop(ack=AsyncMock(), client=mock_client, body=body)

    mock_client.views_open.assert_not_awaited()

# reject_submit → SQS reject + additional_requirements
@pytest.mark.asyncio
async def test_reject_submit_puts_sqs_with_additional(mock_sqs):
    from src.controller.handler.slash import handle_reject_submit
    body = {"user": {"id": "U1"}, "view": {"id": "v1", "private_metadata": '{"message_ts":"ts1","channel_id":"C1","user_id":"U1"}'}}
    view = {
        "id": "v1",
        "private_metadata": '{"message_ts":"ts1","channel_id":"C1","user_id":"U1"}',
        "state": {"values": {"additional_requirements": {"input": {"value": "성능 개선 추가"}}}},
    }
    await handle_reject_submit(ack=AsyncMock(), body=body, view=view)

    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "reject"
    assert payload["message_ts"] == "ts1"
    assert payload["additional_requirements"] == "성능 개선 추가"

# drop_submit → SQS drop_restart + dropped_ids
@pytest.mark.asyncio
async def test_drop_submit_puts_sqs_with_dropped_ids(mock_sqs):
    from src.controller.handler.slash import handle_drop_submit
    body = {"user": {"id": "U1"}, "view": {"id": "v1"}}
    view = {
        "id": "v1",
        "private_metadata": '{"message_ts":"ts1","channel_id":"C1","user_id":"U1"}',
        "state": {"values": {"drop_selection": {"items": {"selected_options": [
            {"value": "new_features::0"},
            {"value": "domain_rules::0"},
        ]}}}},
    }
    await handle_drop_submit(ack=AsyncMock(), body=body, view=view)

    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "drop_restart"
    assert set(payload["dropped_ids"]) == {"new_features::0", "domain_rules::0"}
```

---

### `tests/integration/test_lambda_worker.py`

SQS 이벤트 dict를 Worker Lambda `handler()`에 직접 주입해 전체 흐름 검증.

```
검증 대상:
  pipeline_start  →  read_planner + issue_gen → chat_postMessage → pending.save
  accept          →  pending.delete → chat_update
  reject          →  pending.get → re_issue_generator → chat_postMessage → save_new_and_delete_old
  drop_restart    →  pending.get → drop_items → re_issue_generator → chat_postMessage → save_new_and_delete_old
  duplicate       →  idempotency 차단 → 서비스 미호출
```

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def _sqs_event(body: dict) -> dict:
    return {"Records": [{"body": json.dumps(body)}]}

@pytest.fixture
def mock_slack_client():
    client = AsyncMock()
    client.chat_postMessage = AsyncMock(return_value={"ts": "new_msg_ts"})
    client.chat_update = AsyncMock(return_value={"ok": True})
    return client

@pytest.fixture
def mock_services(feat_template):
    from src.agent.usage import AgentUsage
    with patch("src.lambda_worker.run_read_planner") as planner, \
         patch("src.lambda_worker.run_issue_generator") as gen, \
         patch("src.lambda_worker.run_re_issue_generator") as reissue:
        planner.return_value = ("inspector_out", AgentUsage(10, 5))
        gen.return_value = (feat_template, AgentUsage(20, 8))
        reissue.return_value = (feat_template, AgentUsage(15, 6))
        yield planner, gen, reissue

@pytest.fixture
def mock_repos(feat_template):
    from src.domain.pending import PendingRecord
    record = PendingRecord(
        pk="msg_ts_123", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", inspector_output="{}",
        typed_output=feat_template,
    )
    with patch("src.lambda_worker._pending_repo") as pending, \
         patch("src.lambda_worker._idempotency_repo") as idempotency:
        pending.save = AsyncMock()
        pending.get = AsyncMock(return_value=record)
        pending.delete = AsyncMock()
        pending.save_new_and_delete_old = AsyncMock()
        idempotency.try_acquire = AsyncMock(return_value=True)
        idempotency.mark_done = AsyncMock()
        yield pending, idempotency

# pipeline_start → 서비스 순서 및 DynamoDB 저장
@pytest.mark.asyncio
async def test_pipeline_start_full_flow(mock_services, mock_repos, mock_slack_client):
    from src.lambda_worker import _process
    planner, gen, _ = mock_services
    pending_repo, _ = mock_repos

    with patch("src.lambda_worker.AsyncWebClient", return_value=mock_slack_client), \
         patch("src.lambda_worker.GitHubMCPFactory.connect"), \
         patch("src.lambda_worker.GitHubMCPFactory.disconnect"):
        await _process(json.dumps({
            "type": "pipeline_start",
            "subcommand": "feat",
            "user_id": "U1",
            "channel_id": "C1",
            "user_message": "[feat] 즐겨찾기",
            "dedup_id": "dedup_1",
        }))

    planner.assert_awaited_once_with("[feat] 즐겨찾기")
    gen.assert_awaited_once_with("feat", "inspector_out")
    mock_slack_client.chat_postMessage.assert_awaited_once()
    pending_repo.save.assert_awaited_once()
    saved_record = pending_repo.save.call_args[0][0]
    assert saved_record.pk == "new_msg_ts"  # chat_postMessage 반환값

# accept → pending 삭제 + Slack 메시지 업데이트
@pytest.mark.asyncio
async def test_accept_deletes_record_and_updates_message(mock_repos, mock_slack_client):
    from src.lambda_worker import _process
    pending_repo, _ = mock_repos

    with patch("src.lambda_worker.AsyncWebClient", return_value=mock_slack_client), \
         patch("src.lambda_worker.GitHubMCPFactory.connect"), \
         patch("src.lambda_worker.GitHubMCPFactory.disconnect"):
        await _process(json.dumps({
            "type": "accept",
            "message_ts": "msg_ts_123",
            "user_id": "U1",
            "channel_id": "C1",
            "dedup_id": "dedup_2",
        }))

    pending_repo.delete.assert_awaited_once_with("msg_ts_123")
    mock_slack_client.chat_update.assert_awaited_once()

# reject → re_issue_generator 호출 + DynamoDB rotate
@pytest.mark.asyncio
async def test_reject_calls_reissue_and_rotates_record(mock_services, mock_repos, mock_slack_client):
    from src.lambda_worker import _process
    _, _, reissue = mock_services
    pending_repo, _ = mock_repos

    with patch("src.lambda_worker.AsyncWebClient", return_value=mock_slack_client), \
         patch("src.lambda_worker.GitHubMCPFactory.connect"), \
         patch("src.lambda_worker.GitHubMCPFactory.disconnect"):
        await _process(json.dumps({
            "type": "reject",
            "message_ts": "msg_ts_123",
            "user_id": "U1",
            "channel_id": "C1",
            "additional_requirements": "성능 개선",
            "dedup_id": "dedup_3",
        }))

    reissue.assert_awaited_once()
    reissue_call = reissue.call_args
    assert reissue_call.kwargs.get("additional_requirements") == "성능 개선" \
        or reissue_call.args[1] == "성능 개선"
    pending_repo.save_new_and_delete_old.assert_awaited_once()
    assert pending_repo.save_new_and_delete_old.call_args.kwargs.get("old_ts") == "msg_ts_123" \
        or pending_repo.save_new_and_delete_old.call_args.args[1] == "msg_ts_123"

# drop_restart → drop_items 적용 후 re_issue_generator 호출
@pytest.mark.asyncio
async def test_drop_restart_applies_drop_then_reissues(mock_services, mock_repos, mock_slack_client):
    from src.lambda_worker import _process
    _, _, reissue = mock_services
    pending_repo, _ = mock_repos

    with patch("src.lambda_worker.AsyncWebClient", return_value=mock_slack_client), \
         patch("src.lambda_worker.GitHubMCPFactory.connect"), \
         patch("src.lambda_worker.GitHubMCPFactory.disconnect"), \
         patch("src.lambda_worker.drop_items") as mock_drop:
        mock_drop.return_value = mock_repos[0].get.return_value.typed_output
        await _process(json.dumps({
            "type": "drop_restart",
            "message_ts": "msg_ts_123",
            "user_id": "U1",
            "channel_id": "C1",
            "dropped_ids": ["new_features::0"],
            "dedup_id": "dedup_4",
        }))

    mock_drop.assert_called_once()
    assert set(mock_drop.call_args[0][1]) == {"new_features::0"}
    reissue.assert_awaited_once()

# 중복 dedup_id → 서비스 미호출
@pytest.mark.asyncio
async def test_duplicate_dedup_id_is_skipped(mock_services, mock_repos):
    from src.lambda_worker import _process
    planner, _, _ = mock_services
    _, idempotency_repo = mock_repos
    idempotency_repo.try_acquire = AsyncMock(return_value=False)  # 이미 처리됨

    with patch("src.lambda_worker.AsyncWebClient"), \
         patch("src.lambda_worker.GitHubMCPFactory.connect"), \
         patch("src.lambda_worker.GitHubMCPFactory.disconnect"):
        await _process(json.dumps({
            "type": "pipeline_start",
            "subcommand": "feat",
            "user_id": "U1", "channel_id": "C1",
            "user_message": "msg", "dedup_id": "dup_id",
        }))

    planner.assert_not_awaited()

# pending record 없는 reject → 조기 종료
@pytest.mark.asyncio
async def test_reject_with_missing_record_skips_service(mock_services, mock_repos):
    from src.lambda_worker import _process
    _, _, reissue = mock_services
    pending_repo, _ = mock_repos
    pending_repo.get = AsyncMock(return_value=None)

    with patch("src.lambda_worker.AsyncWebClient"), \
         patch("src.lambda_worker.GitHubMCPFactory.connect"), \
         patch("src.lambda_worker.GitHubMCPFactory.disconnect"):
        await _process(json.dumps({
            "type": "reject",
            "message_ts": "missing_ts",
            "user_id": "U1", "channel_id": "C1",
            "dedup_id": "dedup_5",
        }))

    reissue.assert_not_awaited()
```

---

## 단계별 실행 순서

| Phase | 목표 | 명령 |
|-------|------|------|
| 2 | 도메인 모델 | `pytest tests/unit/domain/ -v` |
| 3 | Controller | `pytest tests/unit/controller/ -v` |
| 4 | Services | `pytest tests/unit/services/ -v` |
| 5 | AgentFactory | `pytest tests/unit/agent/ -v` |
| 6-Ack | Ack Lambda | `pytest tests/integration/test_lambda_ack.py -v` |
| 6-Worker | Worker Lambda | `pytest tests/integration/test_lambda_worker.py -v` |
| 전체 | | `pytest tests/ -v` |
