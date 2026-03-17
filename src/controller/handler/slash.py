"""슬래시 커맨드 / Modal 제출 / Block Action 핸들러 — ack 후 큐 전달."""

import json
import logging

from slack_bolt.async_app import AsyncApp

from src.controller._reply import build_reject_modal, build_drop_modal
from src.controller.issue_drop import droppable_items
from src.controller.modal_templates.feat_modal_input import FeatModalInput
from src.controller.modal_templates.fix_modal_input import FixModalInput
from src.controller.modal_templates.refactor_modal_input import (
    RefactorModalInput,
)
from src.domain.pending import IPendingRepository
from src.domain.queue import IQueueSender

logger = logging.getLogger(__name__)

_pending_repo: IPendingRepository | None = None
_queue: IQueueSender | None = None


def configure(pending_repo: IPendingRepository, queue: IQueueSender) -> None:
    """진입점(Lambda / 로컬 서버)에서 의존성을 주입한다."""
    global _pending_repo, _queue
    _pending_repo = pending_repo
    _queue = queue


def _put_sqs(message: dict) -> None:
    assert _queue is not None, "slash.configure() 가 호출되지 않았습니다"
    _queue.send(message)


def _modal_view(
    callback_id: str,
    title: str,
    blocks: list[dict],
    private_metadata: str = "",
) -> dict:
    return {
        "type": "modal",
        "callback_id": callback_id,
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": title},
        "submit": {"type": "plain_text", "text": "제출"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": blocks,
    }


def register(app: AsyncApp) -> None:

    # ── 슬래시 커맨드 → Modal 열기 ──────────────────────────────────────────

    @app.command("/feat")
    async def handle_feat(ack, client, command):
        await ack()
        await client.views_open(
            trigger_id=command["trigger_id"],
            view=_modal_view(
                FeatModalInput.CALLBACK_ID,
                "기능 요청",
                FeatModalInput.modal_blocks(),
                private_metadata=json.dumps(
                    {"channel_id": command["channel_id"]}
                ),
            ),
        )

    @app.command("/refactor")
    async def handle_refactor(ack, client, command):
        await ack()
        await client.views_open(
            trigger_id=command["trigger_id"],
            view=_modal_view(
                RefactorModalInput.CALLBACK_ID,
                "리팩토링 요청",
                RefactorModalInput.modal_blocks(),
                private_metadata=json.dumps(
                    {"channel_id": command["channel_id"]}
                ),
            ),
        )

    @app.command("/fix")
    async def handle_fix(ack, client, command):
        await ack()
        await client.views_open(
            trigger_id=command["trigger_id"],
            view=_modal_view(
                FixModalInput.CALLBACK_ID,
                "버그 수정 요청",
                FixModalInput.modal_blocks(),
                private_metadata=json.dumps(
                    {"channel_id": command["channel_id"]}
                ),
            ),
        )

    # ── Modal 제출 → 큐 pipeline_start ──────────────────────────────────────

    @app.view(FeatModalInput.CALLBACK_ID)
    async def handle_feat_submit(ack, body, view):
        await ack()
        meta = json.loads(view.get("private_metadata") or "{}")
        _put_sqs({
            "type": "pipeline_start",
            "subcommand": "feat",
            "user_id": body["user"]["id"],
            "channel_id": meta.get("channel_id", ""),
            "user_message": FeatModalInput.from_view(
                view["state"]["values"]
            ).to_prompt(),
            "dedup_id": body["view"]["id"],
        })

    @app.view(RefactorModalInput.CALLBACK_ID)
    async def handle_refactor_submit(ack, body, view):
        await ack()
        meta = json.loads(view.get("private_metadata") or "{}")
        _put_sqs({
            "type": "pipeline_start",
            "subcommand": "refactor",
            "user_id": body["user"]["id"],
            "channel_id": meta.get("channel_id", ""),
            "user_message": RefactorModalInput.from_view(
                view["state"]["values"]
            ).to_prompt(),
            "dedup_id": body["view"]["id"],
        })

    @app.view(FixModalInput.CALLBACK_ID)
    async def handle_fix_submit(ack, body, view):
        await ack()
        meta = json.loads(view.get("private_metadata") or "{}")
        _put_sqs({
            "type": "pipeline_start",
            "subcommand": "fix",
            "user_id": body["user"]["id"],
            "channel_id": meta.get("channel_id", ""),
            "user_message": FixModalInput.from_view(
                view["state"]["values"]
            ).to_prompt(),
            "dedup_id": body["view"]["id"],
        })

    # ── Block Actions ────────────────────────────────────────────────────────

    @app.action("issue_accept")
    async def handle_accept(ack, body):
        await ack()
        _put_sqs({
            "type": "accept",
            "message_ts": body["message"]["ts"],
            "user_id": body["user"]["id"],
            "channel_id": body["channel"]["id"],
            "dedup_id": body["actions"][0]["action_ts"],
        })

    @app.action("issue_reject")
    async def handle_reject(ack, client, body):
        await ack()
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=build_reject_modal(
                message_ts=body["message"]["ts"],
                channel_id=body["channel"]["id"],
                user_id=body["user"]["id"],
            ),
        )

    @app.view("reject_submit")
    async def handle_reject_submit(ack, body, view):
        await ack()
        meta = json.loads(view.get("private_metadata") or "{}")
        additional = (
            view["state"]["values"]
            .get("additional_requirements", {})
            .get("input", {})
            .get("value") or None
        )
        _put_sqs({
            "type": "reject",
            "message_ts": meta["message_ts"],
            "user_id": meta["user_id"],
            "channel_id": meta["channel_id"],
            "additional_requirements": additional,
            "dedup_id": body["view"]["id"],
        })

    @app.action("issue_drop")
    async def handle_drop(ack, client, body):
        await ack()
        assert _pending_repo is not None, "slash.configure() 가 호출되지 않았습니다"
        message_ts = body["message"]["ts"]
        record = await _pending_repo.get(message_ts)
        if not record:
            logger.warning("drop | pending record not found ts=%s", message_ts)
            return
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=build_drop_modal(
                message_ts=message_ts,
                channel_id=body["channel"]["id"],
                user_id=body["user"]["id"],
                items=droppable_items(record.typed_output),
            ),
        )

    @app.view("drop_submit")
    async def handle_drop_submit(ack, body, view):
        await ack()
        meta = json.loads(view.get("private_metadata") or "{}")
        selected = (
            view["state"]["values"]
            .get("drop_selection", {})
            .get("items", {})
            .get("selected_options") or []
        )
        _put_sqs({
            "type": "drop_restart",
            "message_ts": meta["message_ts"],
            "user_id": meta["user_id"],
            "channel_id": meta["channel_id"],
            "dropped_ids": [opt["value"] for opt in selected],
            "dedup_id": body["view"]["id"],
        })
