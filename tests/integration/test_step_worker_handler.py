"""step_worker_handler 통합 테스트."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.app.handlers.step_worker_handler import _process


def _sqs_event(body: dict) -> dict:
    return {"Records": [{"body": json.dumps(body)}]}


def _patch_deps(mock_runtime):
    return [
        patch("src.app.handlers.step_worker_handler.WorkflowRuntime", return_value=mock_runtime),
        patch("src.agent.mcp.GitHubMCPFactory.connect", new_callable=AsyncMock),
        patch("src.agent.mcp.GitHubMCPFactory.disconnect", new_callable=AsyncMock),
        patch("src.app.handlers.step_worker_handler._idempotency_repo"),
    ]


async def test_pipeline_start_calls_runtime_start():
    mock_runtime = AsyncMock()
    mock_runtime.start.return_value = MagicMock(slack_channel_id="C1")

    event = _sqs_event({
        "type": "pipeline_start",
        "workflow_id": "wf-1",
        "subcommand": "feat",
        "channel_id": "C1",
        "user_id": "U1",
        "user_message": "북마크 추가",
    })

    with patch("src.app.handlers.step_worker_handler.WorkflowRuntime", return_value=mock_runtime), \
         patch("src.agent.mcp.GitHubMCPFactory.connect", new_callable=AsyncMock), \
         patch("src.agent.mcp.GitHubMCPFactory.disconnect", new_callable=AsyncMock), \
         patch("src.app.handlers.step_worker_handler._idempotency_repo") as mock_idempotency:
        mock_idempotency.try_acquire = AsyncMock(return_value=True)
        mock_idempotency.mark_done = AsyncMock()
        await _process(event["Records"][0]["body"])

    mock_runtime.start.assert_called_once()
    call_kwargs = mock_runtime.start.call_args[1]
    assert call_kwargs["workflow_type"] == "feat_issue"
    assert call_kwargs["slack_channel_id"] == "C1"
    assert call_kwargs["slack_user_id"] == "U1"
    assert call_kwargs["user_message"] == "북마크 추가"


async def test_accept_calls_runtime_resume():
    mock_runtime = AsyncMock()
    mock_runtime.resume.return_value = MagicMock(slack_channel_id="C1")

    event = _sqs_event({
        "type": "accept",
        "workflow_id": "wf-1",
    })

    with patch("src.app.handlers.step_worker_handler.WorkflowRuntime", return_value=mock_runtime), \
         patch("src.agent.mcp.GitHubMCPFactory.connect", new_callable=AsyncMock), \
         patch("src.agent.mcp.GitHubMCPFactory.disconnect", new_callable=AsyncMock), \
         patch("src.app.handlers.step_worker_handler._idempotency_repo") as mock_idempotency:
        mock_idempotency.try_acquire = AsyncMock(return_value=True)
        mock_idempotency.mark_done = AsyncMock()
        await _process(event["Records"][0]["body"])

    mock_runtime.resume.assert_called_once_with(
        workflow_id="wf-1",
        action="accept",
        feedback=None,
        dropped_ids=None,
    )


async def test_reject_calls_runtime_resume_with_feedback():
    mock_runtime = AsyncMock()
    mock_runtime.resume.return_value = MagicMock(slack_channel_id="C1")

    event = _sqs_event({
        "type": "reject",
        "workflow_id": "wf-2",
        "additional_requirements": "로그인 기능도 포함해줘",
    })

    with patch("src.app.handlers.step_worker_handler.WorkflowRuntime", return_value=mock_runtime), \
         patch("src.agent.mcp.GitHubMCPFactory.connect", new_callable=AsyncMock), \
         patch("src.agent.mcp.GitHubMCPFactory.disconnect", new_callable=AsyncMock), \
         patch("src.app.handlers.step_worker_handler._idempotency_repo") as mock_idempotency:
        mock_idempotency.try_acquire = AsyncMock(return_value=True)
        mock_idempotency.mark_done = AsyncMock()
        await _process(event["Records"][0]["body"])

    mock_runtime.resume.assert_called_once_with(
        workflow_id="wf-2",
        action="reject",
        feedback="로그인 기능도 포함해줘",
        dropped_ids=None,
    )
