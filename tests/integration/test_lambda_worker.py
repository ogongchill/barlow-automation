"""step_worker_handler 통합 테스트 — SQS 이벤트 → WorkflowRuntime 흐름 검증.

외부 연동 mock:
  - _workflow_repo: src.app.handlers.step_worker_handler._workflow_repo
  - _idempotency_repo: src.app.handlers.step_worker_handler._idempotency_repo
  - Slack API: AsyncWebClient
  - GitHub MCP: GitHubMCPFactory
  - WorkflowRuntime: start / resume
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.app.handlers.step_worker_handler import _process


def _event(**kwargs) -> str:
    return json.dumps(kwargs)


@pytest.fixture()
def worker_ctx(mock_workflow_repo, mock_idempotency_repo, mock_slack_client):
    """step_worker_handler 실행에 필요한 모든 mock을 패치하고 컨텍스트를 반환한다."""
    mock_runtime = AsyncMock()
    mock_runtime.start = AsyncMock(return_value=AsyncMock(slack_channel_id="C1"))
    mock_runtime.resume = AsyncMock(return_value=AsyncMock(slack_channel_id="C1"))

    with (
        patch(
            "src.app.handlers.step_worker_handler._workflow_repo",
            mock_workflow_repo,
        ),
        patch(
            "src.app.handlers.step_worker_handler._idempotency_repo",
            mock_idempotency_repo,
        ),
        patch(
            "src.app.handlers.step_worker_handler.AsyncWebClient",
            return_value=mock_slack_client,
        ),
        patch(
            "src.app.handlers.step_worker_handler.WorkflowRuntime",
            return_value=mock_runtime,
        ),
        patch(
            "src.app.handlers.step_worker_handler.GitHubMCPFactory.connect",
            new=AsyncMock(),
        ),
        patch(
            "src.app.handlers.step_worker_handler.GitHubMCPFactory.disconnect",
            new=AsyncMock(),
        ),
    ):
        yield {
            "workflow_repo": mock_workflow_repo,
            "idempotency": mock_idempotency_repo,
            "client": mock_slack_client,
            "runtime": mock_runtime,
        }


# ── pipeline_start ─────────────────────────────────────────────────────────────

async def test_pipeline_start_calls_runtime_start(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="[feat] 즐겨찾기", dedup_id="d1",
    ))
    worker_ctx["runtime"].start.assert_awaited_once()
    call_kwargs = worker_ctx["runtime"].start.call_args.kwargs
    assert call_kwargs["workflow_type"] == "feat_issue"
    assert call_kwargs["slack_user_id"] == "U1"
    assert call_kwargs["slack_channel_id"] == "C1"
    assert call_kwargs["user_message"] == "[feat] 즐겨찾기"


async def test_pipeline_start_marks_idempotency_done(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="d1",
    ))
    worker_ctx["idempotency"].mark_done.assert_awaited_once_with("d1")


async def test_pipeline_start_refactor_workflow_type(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="refactor",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="d1",
    ))
    call_kwargs = worker_ctx["runtime"].start.call_args.kwargs
    assert call_kwargs["workflow_type"] == "refactor_issue"


# ── accept ─────────────────────────────────────────────────────────────────────

async def test_accept_calls_runtime_resume(worker_ctx):
    await _process(_event(
        type="accept", workflow_id="wf-1",
        user_id="U1", channel_id="C1", dedup_id="d2",
    ))
    worker_ctx["runtime"].resume.assert_awaited_once()
    call_kwargs = worker_ctx["runtime"].resume.call_args.kwargs
    assert call_kwargs["workflow_id"] == "wf-1"
    assert call_kwargs["action"] == "accept"


async def test_accept_marks_idempotency_done(worker_ctx):
    await _process(_event(
        type="accept", workflow_id="wf-1",
        user_id="U1", channel_id="C1", dedup_id="d2",
    ))
    worker_ctx["idempotency"].mark_done.assert_awaited_once_with("d2")


# ── reject ─────────────────────────────────────────────────────────────────────

async def test_reject_calls_runtime_resume_with_feedback(worker_ctx):
    await _process(_event(
        type="reject", workflow_id="wf-1",
        user_id="U1", channel_id="C1",
        additional_requirements="성능 개선", dedup_id="d3",
    ))
    worker_ctx["runtime"].resume.assert_awaited_once()
    call_kwargs = worker_ctx["runtime"].resume.call_args.kwargs
    assert call_kwargs["workflow_id"] == "wf-1"
    assert call_kwargs["action"] == "reject"
    assert call_kwargs["feedback"] == "성능 개선"


# ── drop_restart ───────────────────────────────────────────────────────────────

async def test_drop_restart_calls_runtime_resume_with_dropped_ids(worker_ctx):
    await _process(_event(
        type="drop_restart", workflow_id="wf-1",
        user_id="U1", channel_id="C1",
        dropped_ids=["new_features::0", "domain_rules::0"], dedup_id="d4",
    ))
    worker_ctx["runtime"].resume.assert_awaited_once()
    call_kwargs = worker_ctx["runtime"].resume.call_args.kwargs
    assert call_kwargs["action"] == "drop_restart"
    assert call_kwargs["dropped_ids"] == ["new_features::0", "domain_rules::0"]


# ── idempotency ────────────────────────────────────────────────────────────────

async def test_duplicate_dedup_id_skips_runtime(worker_ctx):
    worker_ctx["idempotency"].try_acquire = AsyncMock(return_value=False)
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="dup_id",
    ))
    worker_ctx["runtime"].start.assert_not_awaited()


async def test_unknown_event_type_is_ignored(worker_ctx):
    await _process(_event(type="unknown_type", dedup_id="d99"))
    worker_ctx["runtime"].start.assert_not_awaited()
    worker_ctx["runtime"].resume.assert_not_awaited()


# ── missing workflow_id ────────────────────────────────────────────────────────

async def test_accept_without_workflow_id_skips_resume(worker_ctx):
    await _process(_event(
        type="accept", user_id="U1", channel_id="C1", dedup_id="d5",
    ))
    worker_ctx["runtime"].resume.assert_not_awaited()


# ── error handling ─────────────────────────────────────────────────────────────

async def test_pipeline_start_posts_error_message_when_runtime_fails(worker_ctx):
    worker_ctx["runtime"].start.side_effect = Exception("API timeout")
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="d_err1",
    ))
    worker_ctx["client"].chat_postMessage.assert_awaited()
    call_kwargs = worker_ctx["client"].chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C1"
