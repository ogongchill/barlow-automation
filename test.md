# 단위 테스트 계획 (내부 로직)

외부 연동(AWS, Slack API, OpenAI, MCP) 없이 순수 내부 로직만 검증한다.
`pytest` + `pytest-asyncio` + `unittest.mock`.

---

## 대상 및 테스트 케이스

### `domain/issue.py`

가장 순수한 도메인 로직. 의존성 없음.

```python
# without() — 코드 레벨 항목 제거
def test_feat_without_drops_correct_items():
    template = FeatTemplate(new_features=["A", "B", "C"], ...)
    result = template.without({"new_features::1"})
    assert result.new_features == ["A", "C"]

def test_feat_without_empty_set_returns_same():
    result = template.without(set())
    assert result == template

def test_feat_without_all_items_returns_empty():
    result = template.without({"new_features::0", "new_features::1"})
    assert result.new_features == []

# droppable_items() — id 유일성
def test_droppable_items_ids_are_unique():
    ids = [item.id for item in template.droppable_items()]
    assert len(ids) == len(set(ids))

def test_droppable_items_covers_all_list_fields():
    items = template.droppable_items()
    sections = {item.section for item in items}
    assert "new_features" in sections
    assert "domain_rules" in sections
```

---

### `presentation/view/modals.py`

```python
# from_view() — Slack state.values 파싱
def test_feat_modal_from_view_parses_correctly():
    values = {
        "feature_name": {"input": {"value": "즐겨찾기"}},
        "background":   {"input": {"value": "자주 쓰는 페이지"}},
        "features":     {"input": {"value": "- 추가\n- 조회"}},
        "constraints":  {"input": {"value": "로그인 필요"}},
        "design_requirements": {"input": {"value": None}},
    }
    modal = FeatModalInput.from_view(values)
    assert modal.feature_name == "즐겨찾기"
    assert modal.design_requirements == ""

# to_prompt() — 직렬화 형식
def test_feat_modal_to_prompt_starts_with_header():
    modal = FeatModalInput(feature_name="즐겨찾기", ...)
    assert modal.to_prompt().startswith("[feat] 즐겨찾기")

def test_feat_modal_to_prompt_excludes_empty_design():
    modal = FeatModalInput(..., design_requirements="")
    assert "설계 요구사항" not in modal.to_prompt()

def test_feat_modal_to_prompt_includes_design_when_present():
    modal = FeatModalInput(..., design_requirements="GET /api/bookmark")
    assert "설계 요구사항" in modal.to_prompt()
```

---

### `presentation/view/blocks.py`

```python
# build_issue_blocks() — 버튼 포함 여부
def test_build_issue_blocks_has_three_action_buttons():
    blocks = build_issue_blocks("U123", "내용", "")
    action = next(b for b in blocks if b["type"] == "actions")
    ids = [e["action_id"] for e in action["elements"]]
    assert ids == ["issue_accept", "issue_reject", "issue_drop"]

# 긴 텍스트 분할
def test_build_issue_blocks_splits_text_over_2900():
    blocks = build_issue_blocks("U123", "A" * 6000, "")
    sections = [b for b in blocks if b["type"] == "section"]
    assert len(sections) >= 2

# usage 없을 때 context block 미포함
def test_build_issue_blocks_no_context_block_when_no_usage():
    blocks = build_issue_blocks("U123", "내용", "")
    assert not any(b["type"] == "context" for b in blocks)
```

---

### `agent/factory.py`

MCP 연결 mock 후 올바른 Agent 키가 선택되는지 검증.

```python
@patch("src.agent.mcp.GitHubMCPFactory.readProject")
@patch("src.agent.mcp.GitHubMCPFactory.readProjectTree")
def test_inspector_uses_tree_mcp(mock_tree, mock_project):
    AgentFactory.inspector()
    mock_tree.assert_called_once()
    mock_project.assert_not_called()

def test_issue_gen_selects_correct_agent_key():
    for subcommand, expected in [
        ("feat",     AvailableAgents.FEAT_ISSUE_GEN),
        ("refactor", AvailableAgents.REFACTOR_ISSUE_GEN),
        ("fix",      AvailableAgents.FIX_ISSUE_GEN),
    ]:
        with patch.object(AgentFactory, "_build") as mock_build:
            AgentFactory.issue_gen(subcommand)
            assert mock_build.call_args[0][0] == expected

def test_issue_gen_invalid_subcommand_raises():
    with pytest.raises(KeyError):
        AgentFactory.issue_gen("unknown")
```

---

### `service/issue_pipeline.py`

Agent 호출을 mock해 파이프라인 제어 흐름만 검증.

```python
@pytest.mark.asyncio
async def test_execute_pipeline_calls_inspector_then_issue_gen(mock_factory, mock_say):
    await execute_pipeline("feat", "요청", "U123", "C123", mock_say)

    mock_factory.inspector.return_value.run.assert_awaited_once()
    mock_factory.issue_gen.return_value.run.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_reject_no_change_skips_llm(mock_factory, mock_pending):
    # 변경사항 없으면 LLM 호출 없음
    await handle_reject(message_ts="ts", dropped_ids=set(), additional_request="", ...)
    mock_factory.reissue_gen.return_value.run.assert_not_awaited()

@pytest.mark.asyncio
async def test_handle_reject_applies_without_before_llm(mock_factory, mock_pending):
    # filtered draft가 LLM 입력에 포함되는지
    mock_pending.get.return_value = pending_ctx_with_typed_output
    await handle_reject(message_ts="ts", dropped_ids={"new_features::0"}, ...)

    call_input = mock_factory.reissue_gen.return_value.run.call_args[0][0]
    assert "[Current Issue Draft]" in call_input
    assert "[Inspector Context]" in call_input
```

---

## 실행

```bash
pytest tests/unit/ -v
```

## 디렉토리 구조

```
tests/
└── unit/
    ├── domain/
    │   └── test_issue.py
    ├── presentation/
    │   ├── test_blocks.py
    │   └── test_modals.py
    ├── service/
    │   └── test_issue_pipeline.py
    └── agent/
        └── test_factory.py
```
