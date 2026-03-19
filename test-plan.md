# 테스트 계획

> feature-first domain 구조에 맞게 작성됨.

---

## 목표

| 구분 | 범위 | 외부 연동 |
|------|------|-----------|
| Unit | domain/common, domain/feat, app/workflow_runtime | 없음 (mock) |
| Integration | Lambda 핸들러 전체 흐름 | SQS/DynamoDB/Slack/Agent mock |

## 기술 스택

```
pytest
pytest-asyncio   (asyncio_mode = auto)
unittest.mock    (AsyncMock, MagicMock)
httpx / respx    (GitHub API mock)
```

---

## 디렉토리 구조

```
tests/
  conftest.py
  unit/
    common/
      test_workflow_instance.py    # WorkflowInstance 직렬화/역직렬화, IWorkflowInstanceRepository
      test_step_result.py          # StepResult control_signal 기본값
      test_lifecycle.py            # WorkflowStatus 전이 유효성
    feat/
      test_state.py                # FeatIssueWorkflowState.apply_patch
      test_issue.py                # FeatTemplate.to_github_body()
      test_find_relevant_bc.py     # FindRelevantBcStep.execute() — agent mock
      test_generate_issue_draft.py # GenerateIssueDraftStep.execute() — agent mock
      test_wait_confirmation.py    # WaitConfirmationStep.execute() — Slack block 구조 검증
      test_regenerate_issue_draft.py
      test_create_github_issue.py  # httpx mock (respx)
      test_definition.py           # GRAPH 완결성, RESUME_MAP 키 검증
      test_executor.py             # FeatAgentExecutor.build() AgentKey 매핑
    app/
      test_workflow_runtime_start.py   # start() — WAITING 도달까지 step 순서 검증
      test_workflow_runtime_resume.py  # resume() accept/reject/drop_restart
  integration/
    test_step_worker_handler.py    # SQS 레코드 → _process() 전체 흐름 (WorkflowRuntime mock)
```

---

## Unit 테스트 상세

### common/test_workflow_instance.py

```python
def test_create_sets_first_step():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "msg")
    assert instance.current_step == "find_relevant_bc"
    assert instance.status == WorkflowStatus.CREATED

def test_to_item_from_item_roundtrip():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "msg")
    restored = WorkflowInstance.from_item(instance.to_item())
    assert restored.workflow_id == instance.workflow_id
    assert restored.state.user_message == "msg"
```

### common/test_step_result.py

```python
def test_default_control_signal_is_continue():
    r = StepResult(status="success")
    assert r.control_signal == "continue"

def test_state_patch_default_empty():
    r = StepResult(status="success")
    assert r.state_patch == {}
```

### feat/test_state.py

```python
def test_apply_patch_updates_field():
    state = FeatIssueWorkflowState(user_message="msg")
    state.apply_patch({"bc_candidates": '{"items":[]}'})
    assert state.bc_candidates == '{"items":[]}'

def test_apply_patch_ignores_unknown_field():
    state = FeatIssueWorkflowState(user_message="msg")
    state.apply_patch({"nonexistent": "value"})  # 예외 없이 무시
```

### feat/test_issue.py

```python
def test_to_github_body_contains_goal():
    t = FeatTemplate(issue_title="[FEAT] x", about="about", goal="g",
                     new_features=["f1"], domain_rules=["r1"], additional_info="")
    body = t.to_github_body()
    assert "## 목표" in body
    assert "g" in body

def test_to_github_body_skips_empty_additional_info():
    t = FeatTemplate(issue_title="[FEAT] x", about="about", goal="g",
                     new_features=["f1"], domain_rules=["r1"], additional_info="")
    body = t.to_github_body()
    assert "## 추가사항" not in body
```

### feat/test_find_relevant_bc.py

```python
async def test_execute_returns_bc_candidates_in_patch():
    mock_agent = AsyncMock()
    mock_agent.run.return_value = MagicMock(output='{"items":[]}', usage=MagicMock(input_tokens=10, output_tokens=5))

    with patch("src.domain.feat.steps.find_relevant_bc.FeatAgentExecutor.build", return_value=mock_agent):
        step = FindRelevantBcStep()
        state = FeatIssueWorkflowState(user_message="msg")
        result = await step.execute(state)

    assert result.status == "success"
    assert result.control_signal == "continue"
    assert result.state_patch["bc_candidates"] == '{"items":[]}'
```

### feat/test_create_github_issue.py

```python
async def test_execute_creates_issue_and_returns_url():
    import respx, httpx
    state = FeatIssueWorkflowState(
        user_message="msg",
        issue_draft=FeatTemplate(issue_title="[FEAT] x", about="a", goal="g",
                                  new_features=["f"], domain_rules=["r"],
                                  additional_info="").model_dump_json()
    )
    with respx.mock:
        respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={"html_url": "https://github.com/issues/1"})
        )
        step = CreateGithubIssueStep("feat", owner="owner", repo="repo")
        result = await step.execute(state)

    assert result.status == "success"
    assert result.control_signal == "stop"
    assert result.state_patch["github_issue_url"] == "https://github.com/issues/1"
```

### feat/test_definition.py

```python
def test_graph_all_continue_targets_exist():
    for node in GRAPH.values():
        if node.on_continue:
            assert node.on_continue in GRAPH

def test_resume_map_targets_exist():
    for step_name in RESUME_MAP.values():
        assert step_name in GRAPH

def test_first_step_in_graph():
    assert FIRST_STEP in GRAPH
```

### app/test_workflow_runtime_start.py

```python
async def test_start_executes_steps_until_waiting():
    mock_repo = AsyncMock(spec=IWorkflowInstanceRepository)
    mock_repo.get.return_value = None
    mock_slack = AsyncMock()
    mock_slack.chat_postMessage.return_value = {"ts": "123"}

    # step mock: find_bc(continue) -> generate_draft(continue) -> wait(wait_for_user)
    with patch("src.app.workflow_runtime.FindRelevantBcStep") as bc, \
         patch("src.app.workflow_runtime.GenerateIssueDraftStep") as gen, \
         patch("src.app.workflow_runtime.WaitConfirmationStep") as wait:

        bc.return_value.execute = AsyncMock(return_value=StepResult(
            status="success", control_signal="continue",
            state_patch={"bc_candidates": "{}"}
        ))
        gen.return_value.execute = AsyncMock(return_value=StepResult(
            status="success", control_signal="continue",
            state_patch={"issue_draft": "{}"}
        ))
        wait.return_value.execute = AsyncMock(return_value=StepResult(
            status="waiting", control_signal="wait_for_user",
            user_action_request={"blocks": []}
        ))

        runtime = WorkflowRuntime(repo=mock_repo, slack_client=mock_slack)
        instance = await runtime.start("feat_issue", "C1", "U1", "msg")

    assert instance.status == WorkflowStatus.WAITING
    assert mock_slack.chat_postMessage.called
```

---

## Integration 테스트 상세

### test_step_worker_handler.py

```python
async def test_pipeline_start_calls_runtime_start():
    mock_runtime = AsyncMock()
    event = {"Records": [{"body": json.dumps({
        "type": "pipeline_start",
        "workflow_id": "wf-1",
        "subcommand": "feat",
        "channel_id": "C1",
        "user_id": "U1",
        "user_message": "msg",
    })}]}
    with patch("src.app.handlers.step_worker_handler.WorkflowRuntime", return_value=mock_runtime), \
         patch("src.agent.mcp.GitHubMCPFactory.connect"), \
         patch("src.agent.mcp.GitHubMCPFactory.disconnect"):
        handler(event, None)
    mock_runtime.start.assert_called_once()

async def test_accept_calls_runtime_resume():
    mock_runtime = AsyncMock()
    event = {"Records": [{"body": json.dumps({
        "type": "accept",
        "workflow_id": "wf-1",
    })}]}
    with patch("src.app.handlers.step_worker_handler.WorkflowRuntime", return_value=mock_runtime), \
         patch("src.agent.mcp.GitHubMCPFactory.connect"), \
         patch("src.agent.mcp.GitHubMCPFactory.disconnect"):
        handler(event, None)
    mock_runtime.resume.assert_called_once_with(
        workflow_id="wf-1", action="accept", feedback=None, dropped_ids=None
    )
```

---

## 실행 명령

```bash
# 전체
pytest tests/ -v

# unit만
pytest tests/unit/ -v

# 특정 feature
pytest tests/unit/feat/ -v
```

---

## 통과 기준

- 모든 unit 테스트 통과
- integration 테스트 통과
- `python -c "from src.domain.feat.steps.find_relevant_bc import FindRelevantBcStep"` 성공
- `python -c "from src.domain.common.models.workflow_instance import WorkflowInstance"` 성공
