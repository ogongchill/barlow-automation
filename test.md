# 단위 테스트 계획 (내부 로직)

외부 연동(AWS, Slack API, OpenAI, MCP) 없이 순수 내부 로직만 검증한다.
`pytest` + `pytest-asyncio` + `unittest.mock`.

---

## 디렉토리 구조

```
tests/
└── unit/
    ├── domain/
    │   ├── test_issue_templates.py   # 순수 도메인 모델
    │   └── test_pending.py           # PendingRecord 직렬화
    ├── controller/
    │   ├── test_issue_drop.py        # droppable_items, drop_items
    │   ├── test_reply.py             # Block Kit 빌더
    │   └── test_modal_templates.py   # from_view, to_prompt
    ├── services/
    │   ├── test_read_planner.py
    │   ├── test_issue_generator.py
    │   └── test_re_issue_generator.py
    └── agent/
        └── test_agent_factory.py
```

---

## 대상 및 테스트 케이스

### `domain/issue_templates.py`

순수 데이터 구조. 의존성 없음.

```python
# Label 열거형
def test_label_values():
    assert Label.FEAT.value == "feat"
    assert Label.REFACTOR.value == "refactor"
    assert Label.FIX.value == "fix"

# FeatTemplate — 필드 접근
def test_feat_template_label():
    t = FeatTemplate(issue_title="T", about="A", new_features=[], domain_rules=[], domain_constraints=[])
    assert t.label == Label.FEAT
```

---

### `domain/pending.py`

`PendingRecord` 직렬화/역직렬화 왕복 검증.

```python
def _make_record() -> PendingRecord:
    return PendingRecord(
        pk="1234567890.123456",
        subcommand="feat",
        user_id="U123",
        channel_id="C456",
        user_message="[feat] 즐겨찾기",
        inspector_output='{"request_summary": "..."}',
        typed_output=FeatTemplate(
            issue_title="[FEAT] 즐겨찾기 추가",
            about="자주 방문하는 페이지를 저장한다.",
            new_features=["즐겨찾기 추가", "즐겨찾기 조회"],
            domain_rules=["로그인 사용자만 가능"],
            domain_constraints=["REST API 방식"],
        ),
    )

# to_item → from_item 왕복
def test_pending_record_roundtrip():
    record = _make_record()
    item = record.to_item()
    restored = PendingRecord.from_item(item)

    assert restored.pk == record.pk
    assert restored.subcommand == record.subcommand
    assert restored.typed_output.issue_title == record.typed_output.issue_title
    assert restored.typed_output.new_features == record.typed_output.new_features

# subcommand → 올바른 template 클래스로 복원
def test_pending_record_restores_correct_template_type():
    record = _make_record()
    restored = PendingRecord.from_item(record.to_item())
    assert isinstance(restored.typed_output, FeatTemplate)

# TTL 기본값 설정 확인
def test_pending_record_default_ttl_is_set():
    record = _make_record()
    assert record.ttl > 0
```

---

### `controller/issue_drop.py`

`droppable_items()` / `drop_items()` — `singledispatch` 동작 검증.

```python
def _feat() -> FeatTemplate:
    return FeatTemplate(
        issue_title="T", about="A",
        new_features=["A", "B", "C"],
        domain_rules=["R1"],
        domain_constraints=["C1"],
    )

# droppable_items — id 유일성
def test_droppable_items_ids_are_unique():
    items = droppable_items(_feat())
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))

# droppable_items — 모든 필드 커버
def test_droppable_items_covers_all_sections():
    sections = {i.section for i in droppable_items(_feat())}
    assert "신규 기능" in sections
    assert "도메인 규칙" in sections
    assert "기술 제약" in sections

# droppable_items — id 포맷 확인
def test_droppable_items_id_format():
    items = droppable_items(_feat())
    feat_ids = [i.id for i in items if i.section == "신규 기능"]
    assert feat_ids == ["new_features::0", "new_features::1", "new_features::2"]

# drop_items — 지정 항목 제거
def test_drop_items_removes_correct_item():
    result = drop_items(_feat(), {"new_features::1"})
    assert isinstance(result, FeatTemplate)
    assert result.new_features == ["A", "C"]

# drop_items — 빈 set은 원본 유지
def test_drop_items_empty_set_returns_all():
    result = drop_items(_feat(), set())
    assert result.new_features == ["A", "B", "C"]

# drop_items — 전체 제거
def test_drop_items_removes_all():
    result = drop_items(_feat(), {"new_features::0", "new_features::1", "new_features::2"})
    assert result.new_features == []

# RefactorTemplate drop — goals 단위 제거
def test_drop_items_refactor_removes_goal():
    from src.domain.issue_templates import RefactorTemplate
    Goal = RefactorTemplate._Goal
    t = RefactorTemplate(
        issue_title="T", about="A",
        goals=[Goal(as_is=["old1"], to_be=["new1"]), Goal(as_is=["old2"], to_be=["new2"])],
        domain_rules=[], domain_constraints=[],
    )
    result = drop_items(t, {"goals::0"})
    assert len(result.goals) == 1
    assert result.goals[0].as_is == ["old2"]
```

---

### `controller/_reply.py`

Block Kit 빌더 — Slack API 없이 dict 구조만 검증.

```python
def _feat_template() -> FeatTemplate:
    return FeatTemplate(
        issue_title="[FEAT] 즐겨찾기",
        about="자주 방문하는 페이지를 저장한다.",
        new_features=["즐겨찾기 추가"],
        domain_rules=["로그인 필요"],
        domain_constraints=["REST API"],
    )

# build_issue_blocks — 세 버튼 포함
def test_build_issue_blocks_has_three_action_buttons():
    blocks = build_issue_blocks("U123", _feat_template(), "")
    action = next(b for b in blocks if b["type"] == "actions")
    ids = [e["action_id"] for e in action["elements"]]
    assert ids == ["issue_accept", "issue_reject", "issue_drop"]

# build_issue_blocks — 긴 텍스트 분할
def test_build_issue_blocks_splits_long_text():
    from src.domain.issue_templates import FeatTemplate
    t = FeatTemplate(
        issue_title="T", about="A",
        new_features=["x" * 3000],
        domain_rules=[], domain_constraints=[],
    )
    sections = [b for b in build_issue_blocks(None, t, "") if b["type"] == "section"]
    assert len(sections) >= 2

# build_issue_blocks — usage 없으면 context block 미포함
def test_build_issue_blocks_no_context_when_no_usage():
    blocks = build_issue_blocks("U123", _feat_template(), "")
    assert not any(b["type"] == "context" for b in blocks)

# build_issue_blocks — usage 있으면 context block 포함
def test_build_issue_blocks_has_context_when_usage_present():
    blocks = build_issue_blocks("U123", _feat_template(), "in=100 out=200")
    assert any(b["type"] == "context" for b in blocks)

# build_reject_modal — callback_id, private_metadata
def test_build_reject_modal_structure():
    modal = build_reject_modal("ts123", "C1", "U1")
    assert modal["callback_id"] == "reject_submit"
    meta = json.loads(modal["private_metadata"])
    assert meta["message_ts"] == "ts123"
    assert meta["channel_id"] == "C1"

# build_drop_modal — 옵션 개수
def test_build_drop_modal_option_count():
    from src.controller.issue_drop import DroppableItem
    items = [
        DroppableItem(id="f::0", section="신규 기능", text="A"),
        DroppableItem(id="f::1", section="신규 기능", text="B"),
    ]
    modal = build_drop_modal("ts123", "C1", "U1", items)
    assert modal["callback_id"] == "drop_submit"
    checkbox_block = modal["blocks"][0]
    assert len(checkbox_block["element"]["options"]) == 2
```

---

### `controller/modal_templates/`

`from_view()` / `to_prompt()` — Slack state.values 파싱 및 직렬화.

```python
def _feat_values() -> dict:
    return {
        "feature_name":        {"input": {"value": "즐겨찾기"}},
        "background":          {"input": {"value": "자주 쓰는 페이지"}},
        "features":            {"input": {"value": "- 추가\n- 조회"}},
        "constraints":         {"input": {"value": "로그인 필요"}},
        "design_requirements": {"input": {"value": None}},
    }

# FeatModalInput.from_view — 정상 파싱
def test_feat_modal_from_view_parses_correctly():
    modal = FeatModalInput.from_view(_feat_values())
    assert modal.feature_name == "즐겨찾기"
    assert modal.design_requirements == ""

# FeatModalInput.to_prompt — 헤더 포맷
def test_feat_modal_to_prompt_starts_with_header():
    modal = FeatModalInput.from_view(_feat_values())
    assert modal.to_prompt().startswith("[feat] 즐겨찾기")

# FeatModalInput.to_prompt — design_requirements 비어있으면 미포함
def test_feat_modal_to_prompt_excludes_empty_design():
    modal = FeatModalInput.from_view(_feat_values())
    assert "설계 요구사항" not in modal.to_prompt()

# FeatModalInput.to_prompt — design_requirements 있으면 포함
def test_feat_modal_to_prompt_includes_design_when_present():
    values = {**_feat_values(), "design_requirements": {"input": {"value": "GET /api/bookmark"}}}
    modal = FeatModalInput.from_view(values)
    assert "설계 요구사항" in modal.to_prompt()

# _parse_bullets — 줄바꿈/불릿 정규화
def test_parse_bullets_strips_dash_prefix():
    from src.controller.modal_templates.modal_templates import _parse_bullets
    assert _parse_bullets("- A\n- B\n  C") == ["A", "B", "C"]

def test_parse_bullets_ignores_empty_lines():
    from src.controller.modal_templates.modal_templates import _parse_bullets
    assert _parse_bullets("A\n\nB") == ["A", "B"]
```

---

### `agent/agent_factory.py`

MCP 호출 mock 후 올바른 Agent 키 선택 여부 검증.

```python
@patch("src.agent.agent_factory.GitHubMCPFactory.readProjectTree")
@patch("src.agent.agent_factory.GitHubMCPFactory.readProject")
@patch("src.agent.agent_factory.Agent")
def test_inspector_uses_tree_mcp(mock_agent, mock_project, mock_tree):
    AgentFactory.inspector()
    mock_tree.assert_called_once()
    mock_project.assert_not_called()

@patch("src.agent.agent_factory.GitHubMCPFactory.readProject")
@patch("src.agent.agent_factory.Agent")
@pytest.mark.parametrize("subcommand,expected_key", [
    ("feat",     AvailableAgents.FEAT_ISSUE_GEN),
    ("refactor", AvailableAgents.REFACTOR_ISSUE_GEN),
    ("fix",      AvailableAgents.FIX_ISSUE_GEN),
])
def test_issue_gen_selects_correct_agent_key(mock_agent, mock_project, subcommand, expected_key):
    with patch.object(AgentFactory, "_build") as mock_build:
        AgentFactory.issue_gen(subcommand)
        assert mock_build.call_args[0][0] == expected_key

def test_issue_gen_invalid_subcommand_raises():
    with pytest.raises(KeyError):
        AgentFactory.issue_gen("unknown")

def test_reissue_gen_invalid_subcommand_raises():
    with pytest.raises(KeyError):
        AgentFactory.reissue_gen("unknown")
```

---

### `services/read_planner.py`

Agent 호출을 mock해 2단계 파이프라인 제어 흐름 검증.

```python
@pytest.mark.asyncio
async def test_run_read_planner_calls_planner_then_inspector():
    mock_planner = AsyncMock()
    mock_planner.run.return_value = AgentResult(output="plan_output", usage=AgentUsage(10, 5))

    mock_inspector = AsyncMock()
    mock_inspector.run.return_value = AgentResult(output="inspector_output", usage=AgentUsage(20, 8))

    with patch.object(AgentFactory, "read_planner", return_value=mock_planner), \
         patch.object(AgentFactory, "inspector", return_value=mock_inspector):
        output, usage = await run_read_planner("user message")

    mock_planner.run.assert_awaited_once_with("user message")
    mock_inspector.run.assert_awaited_once_with("plan_output")
    assert output == "inspector_output"

@pytest.mark.asyncio
async def test_run_read_planner_accumulates_usage():
    mock_planner = AsyncMock()
    mock_planner.run.return_value = AgentResult(output="", usage=AgentUsage(10, 5))
    mock_inspector = AsyncMock()
    mock_inspector.run.return_value = AgentResult(output="", usage=AgentUsage(20, 8))

    with patch.object(AgentFactory, "read_planner", return_value=mock_planner), \
         patch.object(AgentFactory, "inspector", return_value=mock_inspector):
        _, usage = await run_read_planner("msg")

    assert usage.input_tokens == 30   # 10 + 20
    assert usage.output_tokens == 13  # 5 + 8
```

---

### `services/issue_generator.py`

```python
@pytest.mark.asyncio
async def test_run_issue_generator_returns_typed_output():
    expected_template = FeatTemplate(
        issue_title="[FEAT] T", about="A",
        new_features=[], domain_rules=[], domain_constraints=[],
    )
    mock_agent = AsyncMock()
    mock_agent.run.return_value = AgentResult(
        output="", usage=AgentUsage(5, 3), typed_output=expected_template
    )

    with patch.object(AgentFactory, "issue_gen", return_value=mock_agent):
        template, usage = await run_issue_generator("feat", "inspector_output")

    mock_agent.run.assert_awaited_once_with("inspector_output")
    assert template is expected_template
    assert usage.input_tokens == 5
```

---

### `services/re_issue_generator.py`

프롬프트 구성 및 reissue_gen 호출 검증.

```python
def _make_pending_record() -> PendingRecord:
    return PendingRecord(
        pk="ts", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="original",
        inspector_output='{"summary": "..."}',
        typed_output=FeatTemplate(
            issue_title="T", about="A",
            new_features=["X"], domain_rules=[], domain_constraints=[],
        ),
    )

@pytest.mark.asyncio
async def test_run_re_issue_generator_prompt_contains_sections():
    record = _make_pending_record()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = AgentResult(
        output="", usage=AgentUsage(1, 1), typed_output=record.typed_output
    )

    with patch.object(AgentFactory, "reissue_gen", return_value=mock_agent):
        await run_re_issue_generator(record)

    prompt = mock_agent.run.call_args[0][0]
    assert "[Inspector Context]" in prompt
    assert "[Current Issue Draft]" in prompt

@pytest.mark.asyncio
async def test_run_re_issue_generator_includes_additional_requirements():
    record = _make_pending_record()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = AgentResult(
        output="", usage=AgentUsage(1, 1), typed_output=record.typed_output
    )

    with patch.object(AgentFactory, "reissue_gen", return_value=mock_agent):
        await run_re_issue_generator(record, additional_requirements="성능 개선 추가")

    prompt = mock_agent.run.call_args[0][0]
    assert "Additional requirements: 성능 개선 추가" in prompt

@pytest.mark.asyncio
async def test_run_re_issue_generator_no_additional_when_none():
    record = _make_pending_record()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = AgentResult(
        output="", usage=AgentUsage(1, 1), typed_output=record.typed_output
    )

    with patch.object(AgentFactory, "reissue_gen", return_value=mock_agent):
        await run_re_issue_generator(record, additional_requirements=None)

    prompt = mock_agent.run.call_args[0][0]
    assert "Additional requirements" not in prompt
```

---

## 실행

```bash
# 전체
pytest tests/unit/ -v

# 모듈별
pytest tests/unit/domain/ -v
pytest tests/unit/controller/ -v
pytest tests/unit/services/ -v
pytest tests/unit/agent/ -v
```

## 설치

```bash
pip install pytest pytest-asyncio
```

`pytest.ini` 또는 `pyproject.toml`:

```ini
[pytest]
asyncio_mode = auto
```
