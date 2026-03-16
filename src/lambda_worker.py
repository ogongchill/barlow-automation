"""Worker Lambda 진입점 — SQS 이벤트를 받아 파이프라인을 실행한다."""

import asyncio
import json
import logging

from slack_sdk.web.async_client import AsyncWebClient

from src.config import config
from src.controller._reply import build_issue_blocks
from src.controller.issue_drop import drop_items
from src.domain.pending import PendingRecord
from src.logging_config import setup_logging
from src.services.issue_generator import run_issue_generator
from src.services.re_issue_generator import run_re_issue_generator
from src.services.read_planner import run_read_planner
from src.storage.idempotency_dynamo_repository import DynamoIdempotencyRepository
from src.storage.request_dynamo_repository import DynamoPendingRepository
from src.agent.mcp import GitHubMCPFactory

setup_logging()
logger = logging.getLogger(__name__)

_pending_repo = DynamoPendingRepository()
_idempotency_repo = DynamoIdempotencyRepository()


async def _handle_pipeline_start(event: dict, client: AsyncWebClient) -> None:
    subcommand = event["subcommand"]
    user_id = event["user_id"]
    channel_id = event["channel_id"]
    user_message = event["user_message"]

    inspector_output, plan_usage = await run_read_planner(user_message)
    template, gen_usage = await run_issue_generator(subcommand, inspector_output)
    plan_usage.add(input_tokens=gen_usage.input_tokens, output_tokens=gen_usage.output_tokens)

    blocks = build_issue_blocks(user_id, template, plan_usage.format())
    response = await client.chat_postMessage(channel=channel_id, blocks=blocks)

    await _pending_repo.save(PendingRecord(
        pk=response["ts"],
        subcommand=subcommand,
        user_id=user_id,
        channel_id=channel_id,
        user_message=user_message,
        inspector_output=inspector_output,
        typed_output=template,
    ))


async def _handle_accept(event: dict, client: AsyncWebClient) -> None:
    message_ts = event["message_ts"]
    channel_id = event["channel_id"]

    await _pending_repo.delete(message_ts)
    await client.chat_update(
        channel=channel_id,
        ts=message_ts,
        text="✅ 이슈가 수락되었습니다.",
        blocks=[],
    )


async def _handle_reject(event: dict, client: AsyncWebClient) -> None:
    message_ts = event["message_ts"]
    user_id = event["user_id"]
    channel_id = event["channel_id"]
    additional_requirements = event.get("additional_requirements")

    record = await _pending_repo.get(message_ts)
    if not record:
        logger.warning("reject | pending record not found ts=%s", message_ts)
        return

    template, usage = await run_re_issue_generator(record, additional_requirements)
    blocks = build_issue_blocks(user_id, template, usage.format())
    response = await client.chat_postMessage(channel=channel_id, blocks=blocks)

    await _pending_repo.save_new_and_delete_old(
        new_record=PendingRecord(
            pk=response["ts"],
            subcommand=record.subcommand,
            user_id=user_id,
            channel_id=channel_id,
            user_message=record.user_message,
            inspector_output=record.inspector_output,
            typed_output=template,
        ),
        old_ts=message_ts,
    )


async def _handle_drop_restart(event: dict, client: AsyncWebClient) -> None:
    message_ts = event["message_ts"]
    user_id = event["user_id"]
    channel_id = event["channel_id"]
    dropped_ids = set(event.get("dropped_ids", []))

    record = await _pending_repo.get(message_ts)
    if not record:
        logger.warning("drop_restart | pending record not found ts=%s", message_ts)
        return

    filtered = drop_items(record.typed_output, dropped_ids)
    template, usage = await run_re_issue_generator(
        PendingRecord(
            pk=record.pk,
            subcommand=record.subcommand,
            user_id=user_id,
            channel_id=channel_id,
            user_message=record.user_message,
            inspector_output=record.inspector_output,
            typed_output=filtered,
        )
    )
    blocks = build_issue_blocks(user_id, template, usage.format())
    response = await client.chat_postMessage(channel=channel_id, blocks=blocks)

    await _pending_repo.save_new_and_delete_old(
        new_record=PendingRecord(
            pk=response["ts"],
            subcommand=record.subcommand,
            user_id=user_id,
            channel_id=channel_id,
            user_message=record.user_message,
            inspector_output=record.inspector_output,
            typed_output=template,
        ),
        old_ts=message_ts,
    )


_HANDLERS = {
    "pipeline_start": _handle_pipeline_start,
    "accept": _handle_accept,
    "reject": _handle_reject,
    "drop_restart": _handle_drop_restart,
}


async def _process(body: str) -> None:
    event = json.loads(body)
    event_type = event.get("type")
    handler_fn = _HANDLERS.get(event_type)
    if not handler_fn:
        logger.warning("unknown SQS message type: %s", event_type)
        return

    dedup_id = event.get("dedup_id", "")
    if dedup_id and not await _idempotency_repo.try_acquire(dedup_id):
        logger.info("duplicate event skipped dedup_id=%s", dedup_id)
        return

    client = AsyncWebClient(token=config.slack_bot_token)
    await GitHubMCPFactory.connect()
    try:
        await handler_fn(event, client)
        if dedup_id:
            await _idempotency_repo.mark_done(dedup_id)
    finally:
        await GitHubMCPFactory.disconnect()


def handler(event, context):
    """AWS Lambda entry point — SQS trigger."""
    async def _run():
        for record in event.get("Records", []):
            await _process(record["body"])

    asyncio.run(_run())
