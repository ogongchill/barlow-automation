# 테스트 계획 (test-plan.md)

> refactor-plan.md의 Workflow Runtime 아키텍처에 맞춰 갱신됨.

---

## 목표

| 구분 | 범위 | 외부 연동 |
|------|------|-----------|
| **Unit** | 도메인 모델, Workflow 모델, Step, Executor, Runtime, Mapper | 없음 (모두 mock) |
| **Integration** | Lambda 핸들러 — 요청 단위 전체 흐름 | SQS·DynamoDB·Slack·Agent mock |

---

## 기술 스택

```
pytest
pytest-asyncio          # asyncio_mode = auto
moto[dynamodb,sqs]      # AWS 서비스 mock
unittest.mock           # boto3, Slack SDK, Executor mock
slack_bolt              # BoltRequest — Ack Lambda 핸들러 테스트
httpx                   # GitHub API mock (respx 또는 unittest.mock)
```

---

## 디렉토리 구조

```
tests/
├── conftest.py
├── unit/
│   ├── domain/
│   │   └── test_issue_entities.py          # issue_templates → domain/issue/entities.py
│   ├── workflow/
│   │   ├── models/
│   │   │   ├── test_workflow_instance.py   # WorkflowInstance 직렬화/역직렬화
│   │   │   ├── test_workflow_state.py      # FeatIssueWorkflowState state_patch 적용
│   │   │   └── test_step_result.py         # StepResult 생성 및 control_signal
│   │   ├── runtime/
│   │   │   ├── test_workflow_runtime.py    # step 실행 → transition → enqueue
│   │   │   └── test_transition_resolver.py # StepResult → 다음 step 결정
│   │   ├── steps/
│   │   │   ├── test_find_relevant_bc_step.py
│   │   │   ├── test_decide_bc_step.py
│   │   │   ├── test_generate_issue_draft_step.py
│   │   │   ├── test_regenerate_issue_draft_step.py
│   │   │   └── test_create_github_issue_step.py
│   │   ├── executors/
│   │   │   └── test_agent_executor.py      # AgentExecutor → agent 라우팅
│   │   └── mappers/
│   │       ├── test_slack_payload_mapper.py
│   │       └── test_github_issue_mapper.py
│   ├── controller/
│   │   ├── test_issue_drop.py              # 기존 유지
│   │   └── test_modal_templates.py         # 기존 유지
│   └── infrastructure/
│       ├── test_workflow_instance_store.py # DynamoDB store CRUD
│       └── test_pending_action_store.py    # idempotency CRUD
└── integration/
    ├── test_lambda_ack_handler.py          # Ack Lambda — Function URL 이벤트
    ├── test_slack_interaction_handler.py   # 버튼·모달 → SQS 전송
    └── test_step_worker_handler.py         # SQS 이벤트 → Workflow Runtime → Slack
```

---

## 공통 Fixture (`tests/conftest.py`)

```python
import pytest
from src.domain.issue.entities import FeatTemplate, RefactorTemplate, FixTemplate
from src.workflow.models.workflow_instance import WorkflowInstance, WorkflowStatus
from src.workflow.models.workflow_state import FeatIssueWorkflowState
from src.workflow.models.step_result import StepResult
from src.agent.usage import AgentUsage
from src.agent.base import AgentResult
from unittest.mock import AsyncMock
import time

@pytest.fixture
def feat_template():
    return FeatTemplate(
        issue_title="[FEAT] 즐겨찾기",
        about="자주 방문하는 페이지를 저장한다.",
        goal="즐겨찾기 기능 추가",
        new_features=["즐겨찾기 추가", "즐겨찾기 조회", "즐겨찾기 삭제"],
        domain_rules=["로그인 사용자만 가능"],
        additional_info="REST API 방식",
    )

@pytest.fixture
def refactor_template():
    Goal = RefactorTemplate._Goal
    return RefactorTemplate(
        issue_title="[REFACTOR] SessionManager 분리",
        about="단일 책임 원칙 위반 해소.",
        goals=[
            Goal(as_is=["SessionManager가 저장소 직접 참조"], to_be=["IStore 인터페이스 주입"]),
        ],
        domain_rules=["기존 API 시그니처 유지"],
        domain_constraints=["Python 3.12+"],
    )

@pytest.fixture
def fix_template():
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

@pytest.fixture
def feat_workflow_state():
    return FeatIssueWorkflowState(user_message="[feat] 즐겨찾기 기능 추가")

@pytest.fixture
def feat_workflow_instance(feat_workflow_state):
    return WorkflowInstance(
        workflow_id="wf-123",
        workflow_type="feat_issue",
        status=WorkflowStatus.RUNNING,
        current_step="find_relevant_bc",
        state=feat_workflow_state,
        pending_action_token=None,
        slack_channel_id="C1",
        slack_user_id="U1",
        slack_message_ts=None,
        created_at=int(time.time()),
        ttl=int(time.time()) + 86400,
    )

@pytest.fixture
def make_agent_result():
    def _make(output: str = "", typed_output=None, in_tokens=10, out_tokens=5):
        return AgentResult(
            output=output,
            usage=AgentUsage(input_tokens=in_tokens, output_tokens=out_tokens),
            typed_output=typed_output,
        )
    return _make

@pytest.fixture
def success_step_result():
    return StepResult(status="success", control_signal="continue")
```

---

## Phase 1 — 도메인 / Workflow 모델 Unit Test

### `tests/unit/domain/test_issue_entities.py`

```python
from src.domain.issue.entities import Label, FeatTemplate

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

### `tests/unit/workflow/models/test_workflow_instance.py`

```python
from src.workflow.models.workflow_instance import WorkflowInstance, WorkflowStatus

def test_workflow_instance_to_item_has_required_keys(feat_workflow_instance):
    item = feat_workflow_instance.to_item()
    for key in ["workflow_id", "workflow_type", "status", "current_step", "state", "ttl"]:
        assert key in item

def test_workflow_instance_roundtrip(feat_workflow_instance):
    restored = WorkflowInstance.from_item(feat_workflow_instance.to_item())
    assert restored.workflow_id == feat_workflow_instance.workflow_id
    assert restored.workflow_type == feat_workflow_instance.workflow_type
    assert restored.status == feat_workflow_instance.status
    assert restored.current_step == feat_workflow_instance.current_step

def test_workflow_instance_default_status_is_created():
    # WorkflowInstance 최초 생성 시 CREATED
    instance = WorkflowInstance.create(
        workflow_type="feat_issue",
        slack_channel_id="C1",
        slack_user_id="U1",
        user_message="test",
    )
    assert instance.status == WorkflowStatus.CREATED

def test_workflow_instance_ttl_positive(feat_workflow_instance):
    assert feat_workflow_instance.ttl > 0
```

### `tests/unit/workflow/models/test_workflow_state.py`

```python
from src.workflow.models.workflow_state import FeatIssueWorkflowState

def test_apply_patch_updates_fields(feat_workflow_state):
    patch = {"bc_candidates": '{"items": []}', "user_feedback": None}
    feat_workflow_state.apply_patch(patch)
    assert feat_workflow_state.bc_candidates is not None

def test_initial_state_all_none_except_user_message(feat_workflow_state):
    assert feat_workflow_state.bc_candidates is None
    assert feat_workflow_state.bc_decision is None
    assert feat_workflow_state.issue_draft is None
    assert feat_workflow_state.github_issue_url is None
```

### `tests/unit/workflow/models/test_step_result.py`

```python
from src.workflow.models.step_result import StepResult

def test_default_control_signal_is_continue():
    result = StepResult(status="success")
    assert result.control_signal == "continue"

def test_wait_for_user_signal():
    result = StepResult(status="waiting", control_signal="wait_for_user")
    assert result.control_signal == "wait_for_user"

def test_state_patch_default_empty():
    result = StepResult(status="success")
    assert result.state_patch == {}
```

---

## Phase 2 — Workflow Runtime Unit Test

### `tests/unit/workflow/runtime/test_transition_resolver.py`

```python
from src.workflow.runtime.transition_resolver import TransitionResolver
from src.workflow.models.step_result import StepResult
from src.workflow.definitions.feat_issue_workflow import FEAT_ISSUE_WORKFLOW

resolver = TransitionResolver(FEAT_ISSUE_WORKFLOW)

def test_continue_signal_moves_to_next_step():
    result = StepResult(status="success", control_signal="continue")
    next_step = resolver.resolve("find_relevant_bc", result)
    assert next_step == "decide_bc"  # 정의된 다음 step

def test_wait_for_user_signal_returns_none():
    result = StepResult(status="waiting", control_signal="wait_for_user")
    next_step = resolver.resolve("decide_bc", result)
    assert next_step is None  # enqueue 없음

def test_explicit_next_step_overrides_default():
    result = StepResult(status="success", control_signal="continue", next_step="regenerate_issue_draft")
    next_step = resolver.resolve("wait_issue_confirmation", result)
    assert next_step == "regenerate_issue_draft"

def test_stop_signal_returns_none():
    result = StepResult(status="success", control_signal="stop")
    next_step = resolver.resolve("create_github_issue", result)
    assert next_step is None
```

### `tests/unit/workflow/runtime/test_workflow_runtime.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.workflow.runtime.workflow_runtime import WorkflowRuntime

@pytest.fixture
def mock_instance_repo(feat_workflow_instance):
    repo = AsyncMock()
    repo.get.return_value = feat_workflow_instance
    repo.save.return_value = None
    return repo

@pytest.fixture
def mock_queue():
    return AsyncMock()

@pytest.fixture
def mock_step_registry():
    step = AsyncMock()
    from src.workflow.models.step_result import StepResult
    step.execute.return_value = StepResult(
        status="success",
        control_signal="continue",
        state_patch={"bc_candidates": '{"items":[]}'},
    )
    return {"find_relevant_bc": step}

async def test_runtime_executes_step_and_enqueues_next(
    mock_instance_repo, mock_queue, mock_step_registry, feat_workflow_instance
):
    runtime = WorkflowRuntime(
        instance_repo=mock_instance_repo,
        queue=mock_queue,
        step_registry=mock_step_registry,
    )
    await runtime.run_step(feat_workflow_instance.workflow_id, "find_relevant_bc")

    mock_step_registry["find_relevant_bc"].execute.assert_awaited_once()
    mock_queue.enqueue.assert_awaited_once()  # 다음 step enqueue

async def test_runtime_does_not_enqueue_on_wait_for_user(
    mock_instance_repo, mock_queue, mock_step_registry, feat_workflow_instance
):
    from src.workflow.models.step_result import StepResult
    mock_step_registry["find_relevant_bc"].execute.return_value = StepResult(
        status="waiting", control_signal="wait_for_user"
    )
    runtime = WorkflowRuntime(
        instance_repo=mock_instance_repo,
        queue=mock_queue,
        step_registry=mock_step_registry,
    )
    await runtime.run_step(feat_workflow_instance.workflow_id, "find_relevant_bc")

    mock_queue.enqueue.assert_not_awaited()

async def test_runtime_saves_updated_instance_after_step(
    mock_instance_repo, mock_queue, mock_step_registry, feat_workflow_instance
):
    runtime = WorkflowRuntime(
        instance_repo=mock_instance_repo,
        queue=mock_queue,
        step_registry=mock_step_registry,
    )
    await runtime.run_step(feat_workflow_instance.workflow_id, "find_relevant_bc")

    mock_instance_repo.save.assert_awaited_once()
```

---

## Phase 3 — Step Unit Test

### `tests/unit/workflow/steps/test_find_relevant_bc_step.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.workflow.steps.feat_issue.find_relevant_bc_step import FindRelevantBcStep
from src.workflow.models.workflow_state import FeatIssueWorkflowState

async def test_step_returns_success_result(feat_workflow_state, make_agent_result):
    step = FindRelevantBcStep()
    mock_executor = AsyncMock()
    mock_executor.run.return_value = make_agent_result(output='{"items":[]}')

    with patch("src.workflow.steps.feat_issue.find_relevant_bc_step.AgentExecutor", return_value=mock_executor):
        result = await step.execute(feat_workflow_state)

    assert result.status == "success"
    assert result.control_signal == "continue"

async def test_step_patches_bc_candidates(feat_workflow_state, make_agent_result):
    step = FindRelevantBcStep()
    mock_executor = AsyncMock()
    mock_executor.run.return_value = make_agent_result(output='{"items":[{"bounded_context":"OrderContext"}]}')

    with patch("src.workflow.steps.feat_issue.find_relevant_bc_step.AgentExecutor", return_value=mock_executor):
        result = await step.execute(feat_workflow_state)

    assert "bc_candidates" in result.state_patch

async def test_step_receives_user_message(feat_workflow_state, make_agent_result):
    step = FindRelevantBcStep()
    mock_executor = AsyncMock()
    mock_executor.run.return_value = make_agent_result(output='{"items":[]}')

    with patch("src.workflow.steps.feat_issue.find_relevant_bc_step.AgentExecutor", return_value=mock_executor):
        await step.execute(feat_workflow_state)

    call_args = mock_executor.run.call_args[0][0]
    assert feat_workflow_state.user_message in call_args
```

### `tests/unit/workflow/steps/test_generate_issue_draft_step.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.workflow.steps.feat_issue.generate_issue_draft_step import GenerateIssueDraftStep
from src.workflow.models.workflow_state import FeatIssueWorkflowState

@pytest.fixture
def state_with_bc_decision():
    state = FeatIssueWorkflowState(user_message="[feat] 즐겨찾기")
    state.bc_candidates = '{"items":[{"bounded_context":"OrderContext"}]}'
    state.bc_decision = '{"primary_context":"OrderContext","rationale":"..."}'
    return state

async def test_prompt_includes_bc_decision(state_with_bc_decision, make_agent_result, feat_template):
    step = GenerateIssueDraftStep(subcommand="feat")
    mock_executor = AsyncMock()
    mock_executor.run.return_value = make_agent_result(output="", typed_output=feat_template)

    with patch("src.workflow.steps.feat_issue.generate_issue_draft_step.AgentExecutor", return_value=mock_executor):
        await step.execute(state_with_bc_decision)

    prompt = mock_executor.run.call_args[0][0]
    assert "OrderContext" in prompt

async def test_result_patches_issue_draft(state_with_bc_decision, make_agent_result, feat_template):
    step = GenerateIssueDraftStep(subcommand="feat")
    mock_executor = AsyncMock()
    mock_executor.run.return_value = make_agent_result(output="", typed_output=feat_template)

    with patch("src.workflow.steps.feat_issue.generate_issue_draft_step.AgentExecutor", return_value=mock_executor):
        result = await step.execute(state_with_bc_decision)

    assert "issue_draft" in result.state_patch
```

### `tests/unit/workflow/steps/test_create_github_issue_step.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.workflow.steps.feat_issue.create_github_issue_step import CreateGithubIssueStep
from src.workflow.models.workflow_state import FeatIssueWorkflowState

@pytest.fixture
def state_with_issue_draft(feat_template):
    state = FeatIssueWorkflowState(user_message="[feat] 즐겨찾기")
    state.issue_draft = feat_template.model_dump_json()
    return state

async def test_step_calls_github_api(state_with_issue_draft, feat_template):
    step = CreateGithubIssueStep(subcommand="feat")
    mock_github = AsyncMock()
    mock_github.create_issue.return_value = "https://github.com/owner/repo/issues/1"

    with patch("src.workflow.steps.feat_issue.create_github_issue_step.GitHubClient", return_value=mock_github):
        result = await step.execute(state_with_issue_draft)

    mock_github.create_issue.assert_awaited_once()
    assert result.status == "success"
    assert "github_issue_url" in result.state_patch

async def test_github_payload_includes_title(state_with_issue_draft, feat_template):
    step = CreateGithubIssueStep(subcommand="feat")
    mock_github = AsyncMock()
    mock_github.create_issue.return_value = "https://github.com/owner/repo/issues/2"

    with patch("src.workflow.steps.feat_issue.create_github_issue_step.GitHubClient", return_value=mock_github):
        await step.execute(state_with_issue_draft)

    payload = mock_github.create_issue.call_args[0][0]
    assert feat_template.issue_title in payload["title"]
```

---

## Phase 4 — Executor Unit Test

### `tests/unit/workflow/executors/test_agent_executor.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from src.workflow.executors.agent_executor import AgentExecutor
from src.workflow.models.lifecycle import AgentKey

def test_feat_issue_gen_uses_read_project_mcp():
    with patch("src.workflow.executors.agent_executor.GitHubMCPFactory.readProject") as mock_mcp, \
         patch("src.workflow.executors.agent_executor.Agent"):
        AgentExecutor.build(AgentKey.FEAT_ISSUE_GEN)
        mock_mcp.assert_called_once()

def test_relevant_bc_finder_uses_read_tree_mcp():
    with patch("src.workflow.executors.agent_executor.GitHubMCPFactory.readProjectTree") as mock_tree, \
         patch("src.workflow.executors.agent_executor.Agent"):
        AgentExecutor.build(AgentKey.RELEVANT_BC_FINDER)
        mock_tree.assert_called_once()

def test_invalid_agent_key_raises():
    with pytest.raises((KeyError, ValueError)):
        AgentExecutor.build("unknown_key")
```

---

## Phase 5 — Mapper Unit Test

### `tests/unit/workflow/mappers/test_slack_payload_mapper.py`

```python
from src.workflow.mappers.slack_payload_mapper import (
    build_issue_blocks, build_bc_decision_blocks,
    build_reject_modal, build_drop_modal, build_bc_reject_modal,
)
from src.controller.issue_drop import DroppableItem

def test_build_issue_blocks_has_three_buttons(feat_template):
    blocks = build_issue_blocks("U1", feat_template, "")
    action = next(b for b in blocks if b["type"] == "actions")
    ids = [e["action_id"] for e in action["elements"]]
    assert ids == ["issue_accept", "issue_reject", "issue_drop"]

def test_build_bc_decision_blocks_has_two_buttons():
    bc_decision_json = '{"primary_context":"OrderContext","rationale":"..","mapping_summary":"..","selected_contexts":[],"validation_points":[],"decision":"reuse_existing","new_bc_needed":false,"supporting_contexts":[],"issue_focus":"."}'
    blocks = build_bc_decision_blocks("U1", bc_decision_json, "")
    action = next(b for b in blocks if b["type"] == "actions")
    ids = [e["action_id"] for e in action["elements"]]
    assert "bc_accept" in ids
    assert "bc_reject" in ids

def test_build_reject_modal_callback_id():
    assert build_reject_modal("ts1", "C1", "U1")["callback_id"] == "reject_submit"

def test_build_bc_reject_modal_callback_id():
    assert build_bc_reject_modal("ts1", "C1", "U1")["callback_id"] == "bc_reject_submit"
```

### `tests/unit/workflow/mappers/test_github_issue_mapper.py`

```python
from src.workflow.mappers.github_issue_mapper import build_github_issue_payload

def test_payload_includes_title(feat_template):
    payload = build_github_issue_payload(feat_template)
    assert feat_template.issue_title in payload["title"]

def test_payload_includes_label(feat_template):
    payload = build_github_issue_payload(feat_template)
    assert "feat" in payload.get("labels", [])

def test_payload_body_is_markdown(feat_template):
    payload = build_github_issue_payload(feat_template)
    assert isinstance(payload["body"], str)
    assert len(payload["body"]) > 0
```

---

## Phase 6 — Controller Unit Test (기존 유지)

### `tests/unit/controller/test_issue_drop.py`

기존 내용 유지. (droppable_items, drop_items 검증)

### `tests/unit/controller/test_modal_templates.py`

기존 내용 유지. (FeatModalInput, RefactorModalInput, FixModalInput 파싱)

---

## Phase 7 — Infrastructure Unit Test

### `tests/unit/infrastructure/test_workflow_instance_store.py`

```python
import pytest
import boto3
from moto import mock_aws
from src.infrastructure.storage.dynamodb.workflow_instance_store import DynamoWorkflowInstanceStore

TABLE_NAME = "barlow-workflow"

@pytest.fixture
def dynamo_table():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ap-northeast-2")
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "workflow_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "workflow_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield

async def test_save_and_get_roundtrip(dynamo_table, feat_workflow_instance):
    store = DynamoWorkflowInstanceStore(table_name=TABLE_NAME)
    await store.save(feat_workflow_instance)
    restored = await store.get(feat_workflow_instance.workflow_id)
    assert restored.workflow_id == feat_workflow_instance.workflow_id
    assert restored.status == feat_workflow_instance.status

async def test_get_nonexistent_returns_none(dynamo_table):
    store = DynamoWorkflowInstanceStore(table_name=TABLE_NAME)
    result = await store.get("nonexistent-id")
    assert result is None

async def test_save_overwrites_existing(dynamo_table, feat_workflow_instance):
    from src.workflow.models.lifecycle import WorkflowStatus
    store = DynamoWorkflowInstanceStore(table_name=TABLE_NAME)
    await store.save(feat_workflow_instance)
    feat_workflow_instance.status = WorkflowStatus.COMPLETED
    await store.save(feat_workflow_instance)
    restored = await store.get(feat_workflow_instance.workflow_id)
    assert restored.status == WorkflowStatus.COMPLETED
```

### `tests/unit/infrastructure/test_pending_action_store.py`

```python
import pytest
import boto3
from moto import mock_aws
from src.infrastructure.storage.dynamodb.pending_action_store import DynamoPendingActionStore

TABLE_NAME = "barlow-pending-action"

@pytest.fixture
def dynamo_table():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ap-northeast-2")
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield

async def test_try_acquire_returns_true_first_time(dynamo_table):
    store = DynamoPendingActionStore(table_name=TABLE_NAME)
    assert await store.try_acquire("action-1") is True

async def test_try_acquire_returns_false_for_duplicate(dynamo_table):
    store = DynamoPendingActionStore(table_name=TABLE_NAME)
    await store.try_acquire("action-1")
    assert await store.try_acquire("action-1") is False
```

---

## Phase 8 — Integration Test

### `tests/integration/test_lambda_ack_handler.py`

기존 유지. (`handler()` — Lambda Function URL 이벤트 형식)

### `tests/integration/test_slack_interaction_handler.py`

```
검증 대상:
  /feat, /refactor, /fix     → views_open (modal)
  feat_submit 등             → IQueueSender.send(type=pipeline_start)
  issue_accept               → IQueueSender.send(type=accept)
  issue_reject               → views_open(reject_modal)
  issue_drop                 → WorkflowInstance 조회 → views_open(drop_modal)
  reject_submit              → IQueueSender.send(type=reject) + additional_requirements
  drop_submit                → IQueueSender.send(type=drop_restart) + dropped_ids
  bc_accept                  → IQueueSender.send(type=bc_accept)
  bc_reject 버튼             → views_open(bc_reject_modal)
  bc_reject_submit           → IQueueSender.send(type=bc_reject) + feedback
```

### `tests/integration/test_step_worker_handler.py`

```
검증 대상:
  pipeline_start  → WorkflowRuntime.start() → find_relevant_bc step enqueue
  step_execute    → WorkflowRuntime.run_step() → state 갱신 → 다음 step enqueue or WAITING
  bc_accept       → WorkflowRuntime.resume() → generate_issue_draft step 실행
  bc_reject       → WorkflowRuntime.resume() → find_relevant_bc step 재실행
  accept          → WorkflowRuntime.resume() → create_github_issue step 실행
  reject          → WorkflowRuntime.resume() → regenerate_issue_draft step 실행
  drop_restart    → WorkflowRuntime.resume() → regenerate_issue_draft step 실행 (drop 정보 포함)
  duplicate       → idempotency 차단 → WorkflowRuntime 미호출
  missing record  → 조기 종료
```

```python
import json
import pytest
from unittest.mock import AsyncMock, patch

def _sqs_event(body: dict) -> dict:
    return {"Records": [{"body": json.dumps(body, ensure_ascii=False)}]}

@pytest.fixture
def mock_runtime():
    with patch("src.app.handlers.step_worker_handler.WorkflowRuntime") as cls:
        instance = AsyncMock()
        cls.return_value = instance
        yield instance

async def test_pipeline_start_calls_runtime_start(mock_runtime):
    from src.app.handlers.step_worker_handler import handler
    handler(_sqs_event({
        "type": "pipeline_start",
        "subcommand": "feat",
        "user_id": "U1",
        "channel_id": "C1",
        "user_message": "[feat] 즐겨찾기",
        "dedup_id": "d1",
    }), None)
    mock_runtime.start.assert_awaited_once()

async def test_accept_resumes_runtime_with_accept_action(mock_runtime):
    from src.app.handlers.step_worker_handler import handler
    handler(_sqs_event({
        "type": "accept",
        "workflow_id": "wf-123",
        "action_token": "tok-abc",
        "user_id": "U1",
        "channel_id": "C1",
        "dedup_id": "d2",
    }), None)
    mock_runtime.resume.assert_awaited_once()
    call_kwargs = mock_runtime.resume.call_args
    assert "accept" in str(call_kwargs)

async def test_duplicate_dedup_skips_runtime(mock_runtime):
    from src.app.handlers.step_worker_handler import handler
    with patch("src.app.handlers.step_worker_handler._idempotency_repo") as mock_repo:
        mock_repo.try_acquire = AsyncMock(return_value=False)
        handler(_sqs_event({
            "type": "pipeline_start", "subcommand": "feat",
            "user_id": "U1", "channel_id": "C1",
            "user_message": "msg", "dedup_id": "dup",
        }), None)
    mock_runtime.start.assert_not_awaited()
```

---

## 단계별 실행 순서

| Phase | 대상 | 명령 |
|-------|------|------|
| 1 | 도메인 + Workflow 모델 | `pytest tests/unit/domain/ tests/unit/workflow/models/ -v` |
| 2 | Workflow Runtime | `pytest tests/unit/workflow/runtime/ -v` |
| 3 | Steps | `pytest tests/unit/workflow/steps/ -v` |
| 4 | Executors | `pytest tests/unit/workflow/executors/ -v` |
| 5 | Mappers | `pytest tests/unit/workflow/mappers/ -v` |
| 6 | Controller (기존) | `pytest tests/unit/controller/ -v` |
| 7 | Infrastructure | `pytest tests/unit/infrastructure/ -v` |
| 8-Ack | Ack Lambda | `pytest tests/integration/test_lambda_ack_handler.py -v` |
| 8-Interaction | Slack 인터랙션 | `pytest tests/integration/test_slack_interaction_handler.py -v` |
| 8-Worker | Step Worker | `pytest tests/integration/test_step_worker_handler.py -v` |
| 전체 | | `pytest tests/ -v` |
