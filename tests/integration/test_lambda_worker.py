"""Worker Lambda 통합 테스트 — SQS 이벤트 → 서비스 → Slack 흐름 검증.

외부 연동 mock:
  - DynamoDB: src.lambda_worker._pending_repo / _idempotency_repo
  - Slack API: src.lambda_worker.AsyncWebClient
  - GitHub MCP: src.lambda_worker.GitHubMCPFactory
  - Agent 서비스: run_read_planner, run_issue_generator, run_re_issue_generator
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lambda_worker import _process


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _event(**kwargs) -> str:
    return json.dumps(kwargs)


@pytest.fixture()
def worker_ctx(mock_pending_repo, mock_idempotency_repo, mock_slack_client, mock_services):
    """Worker Lambda 실행에 필요한 모든 mock을 패치하고 컨텍스트를 반환한다."""
    with (
        patch("src.lambda_worker._pending_repo", mock_pending_repo),
        patch("src.lambda_worker._idempotency_repo", mock_idempotency_repo),
        patch("src.lambda_worker.AsyncWebClient", return_value=mock_slack_client),
        patch("src.lambda_worker.GitHubMCPFactory.connect", new=AsyncMock()),
        patch("src.lambda_worker.GitHubMCPFactory.disconnect", new=AsyncMock()),
    ):
        yield {
            "pending": mock_pending_repo,
            "idempotency": mock_idempotency_repo,
            "client": mock_slack_client,
            "services": mock_services,
        }


# ── pipeline_start ────────────────────────────────────────────────────────────

async def test_pipeline_start_calls_read_planner(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="[feat] 즐겨찾기", dedup_id="d1",
    ))
    worker_ctx["services"]["run_read_planner"].assert_awaited_once_with("[feat] 즐겨찾기")


async def test_pipeline_start_calls_issue_gen_with_inspector_output(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="d1",
    ))
    worker_ctx["services"]["run_issue_generator"].assert_awaited_once_with(
        "feat", "inspector output text"
    )


async def test_pipeline_start_posts_to_slack(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="d1",
    ))
    worker_ctx["client"].chat_postMessage.assert_awaited_once()
    call_kwargs = worker_ctx["client"].chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C1"
    assert "blocks" in call_kwargs


async def test_pipeline_start_saves_pending_record_with_new_ts(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="d1",
    ))
    worker_ctx["pending"].save.assert_awaited_once()
    saved = worker_ctx["pending"].save.call_args[0][0]
    assert saved.pk == "new_ts"  # chat_postMessage 반환값의 ts
    assert saved.subcommand == "feat"
    assert saved.user_id == "U1"


async def test_pipeline_start_marks_idempotency_done(worker_ctx):
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="d1",
    ))
    worker_ctx["idempotency"].mark_done.assert_awaited_once_with("d1")


# ── accept ────────────────────────────────────────────────────────────────────

async def test_accept_deletes_pending_record(worker_ctx):
    await _process(_event(
        type="accept", message_ts="msg_ts_123",
        user_id="U1", channel_id="C1", dedup_id="d2",
    ))
    worker_ctx["pending"].delete.assert_awaited_once_with("msg_ts_123")


async def test_accept_updates_slack_message(worker_ctx):
    await _process(_event(
        type="accept", message_ts="msg_ts_123",
        user_id="U1", channel_id="C1", dedup_id="d2",
    ))
    worker_ctx["client"].chat_update.assert_awaited_once()
    call_kwargs = worker_ctx["client"].chat_update.call_args.kwargs
    assert call_kwargs["channel"] == "C1"
    assert call_kwargs["ts"] == "msg_ts_123"


# ── reject ────────────────────────────────────────────────────────────────────

async def test_reject_calls_reissue_generator(worker_ctx):
    await _process(_event(
        type="reject", message_ts="msg_ts_123",
        user_id="U1", channel_id="C1",
        additional_requirements="성능 개선", dedup_id="d3",
    ))
    worker_ctx["services"]["run_re_issue_generator"].assert_awaited_once()
    call_args = worker_ctx["services"]["run_re_issue_generator"].call_args
    assert call_args.kwargs.get("additional_requirements") == "성능 개선" \
        or call_args.args[1] == "성능 개선"


async def test_reject_posts_new_message(worker_ctx):
    await _process(_event(
        type="reject", message_ts="msg_ts_123",
        user_id="U1", channel_id="C1",
        additional_requirements=None, dedup_id="d3",
    ))
    worker_ctx["client"].chat_postMessage.assert_awaited_once()


async def test_reject_rotates_pending_record(worker_ctx):
    await _process(_event(
        type="reject", message_ts="msg_ts_123",
        user_id="U1", channel_id="C1",
        additional_requirements=None, dedup_id="d3",
    ))
    worker_ctx["pending"].save_new_and_delete_old.assert_awaited_once()
    call_kwargs = worker_ctx["pending"].save_new_and_delete_old.call_args.kwargs
    old_ts = call_kwargs.get("old_ts") or worker_ctx["pending"].save_new_and_delete_old.call_args.args[1]
    assert old_ts == "msg_ts_123"


async def test_reject_with_missing_record_skips_service(worker_ctx):
    worker_ctx["pending"].get = AsyncMock(return_value=None)
    await _process(_event(
        type="reject", message_ts="missing_ts",
        user_id="U1", channel_id="C1",
        additional_requirements=None, dedup_id="d3",
    ))
    worker_ctx["services"]["run_re_issue_generator"].assert_not_awaited()


# ── drop_restart ──────────────────────────────────────────────────────────────

async def test_drop_restart_calls_drop_items(worker_ctx):
    with patch("src.lambda_worker.drop_items") as mock_drop:
        mock_drop.return_value = worker_ctx["pending"].get.return_value.typed_output
        await _process(_event(
            type="drop_restart", message_ts="msg_ts_123",
            user_id="U1", channel_id="C1",
            dropped_ids=["new_features::0", "domain_rules::0"], dedup_id="d4",
        ))

    mock_drop.assert_called_once()
    _, dropped_ids_arg = mock_drop.call_args[0]
    assert dropped_ids_arg == {"new_features::0", "domain_rules::0"}


async def test_drop_restart_calls_reissue_generator(worker_ctx):
    with patch("src.lambda_worker.drop_items") as mock_drop:
        mock_drop.return_value = worker_ctx["pending"].get.return_value.typed_output
        await _process(_event(
            type="drop_restart", message_ts="msg_ts_123",
            user_id="U1", channel_id="C1",
            dropped_ids=["new_features::0"], dedup_id="d4",
        ))

    worker_ctx["services"]["run_re_issue_generator"].assert_awaited_once()


async def test_drop_restart_rotates_pending_record(worker_ctx):
    with patch("src.lambda_worker.drop_items") as mock_drop:
        mock_drop.return_value = worker_ctx["pending"].get.return_value.typed_output
        await _process(_event(
            type="drop_restart", message_ts="msg_ts_123",
            user_id="U1", channel_id="C1",
            dropped_ids=[], dedup_id="d4",
        ))

    worker_ctx["pending"].save_new_and_delete_old.assert_awaited_once()


async def test_drop_restart_with_missing_record_skips(worker_ctx):
    worker_ctx["pending"].get = AsyncMock(return_value=None)
    await _process(_event(
        type="drop_restart", message_ts="missing_ts",
        user_id="U1", channel_id="C1",
        dropped_ids=[], dedup_id="d4",
    ))
    worker_ctx["services"]["run_re_issue_generator"].assert_not_awaited()


# ── idempotency ───────────────────────────────────────────────────────────────

async def test_duplicate_dedup_id_skips_all_services(worker_ctx):
    worker_ctx["idempotency"].try_acquire = AsyncMock(return_value=False)
    await _process(_event(
        type="pipeline_start", subcommand="feat",
        user_id="U1", channel_id="C1",
        user_message="msg", dedup_id="dup_id",
    ))
    worker_ctx["services"]["run_read_planner"].assert_not_awaited()
    worker_ctx["services"]["run_issue_generator"].assert_not_awaited()
    worker_ctx["client"].chat_postMessage.assert_not_awaited()


async def test_unknown_event_type_is_ignored(worker_ctx):
    await _process(_event(type="unknown_type", dedup_id="d99"))
    worker_ctx["services"]["run_read_planner"].assert_not_awaited()
