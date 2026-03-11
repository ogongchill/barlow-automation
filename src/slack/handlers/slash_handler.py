"""Slash command 이벤트 핸들러."""

import logging
from dataclasses import dataclass

from slack_bolt.async_app import AsyncApp

from src.agent.agents.agent_factory import OpenAiAgentFactory
from src.agent.agents.issue_templates import BaseIssueTemplate, DroppableItem
from src.agent.runner.openai import OpenAIAgent
from src.session.manager import ISessionManager
from src.slack.handlers._reply import build_issue_blocks
from src.slack.handlers.slash_modal_templates import FeatModalInput, RefactorModalInput, FixModalInput

logger = logging.getLogger(__name__)


@dataclass
class _IssueContext:
    subcommand: str
    user_message: str      # 드롭 시 처음부터 재실행하기 위해 보관
    inspector_output: str  # 재요청 시 inspector 재실행 없이 재사용
    typed_output: BaseIssueTemplate  # 드롭 항목 선택 Modal용


# (channel, user) → _IssueContext. 수락/재요청/드롭 대기 중인 이슈 컨텍스트를 보관한다.
_pending: dict[tuple[str, str], _IssueContext] = {}


def _issue_agent(subcommand: str) -> OpenAIAgent:
    if subcommand == "feat":
        return OpenAiAgentFactory.feat_issue_gen()
    elif subcommand == "refactor":
        return OpenAiAgentFactory.refactor_issue_gen()
    else:
        return OpenAiAgentFactory.fix_issue_gen()


def _reissue_agent(subcommand: str) -> OpenAIAgent:
    if subcommand == "feat":
        return OpenAiAgentFactory.feat_reissue_gen()
    elif subcommand == "refactor":
        return OpenAiAgentFactory.refactor_reissue_gen()
    else:
        return OpenAiAgentFactory.fix_reissue_gen()


def _build_reject_modal_blocks(droppable: list[DroppableItem]) -> list[dict]:
    """드롭 항목 선택 Modal의 Block Kit 블록을 생성한다."""
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "제외할 항목의 *체크를 해제*하세요. 체크된 항목만 재생성에 포함됩니다.",
            },
        }
    ]

    # 섹션별로 그룹핑 (입력 순서 유지)
    section_groups: dict[str, list[DroppableItem]] = {}
    for item in droppable:
        section_groups.setdefault(item.section, []).append(item)

    for idx, (section_label, items) in enumerate(section_groups.items()):
        options = [
            {
                "text": {"type": "plain_text", "text": item.text[:74]},
                "value": item.id,
            }
            for item in items
        ]
        blocks.append({
            "type": "input",
            "block_id": f"drop_{idx}",
            "optional": True,
            "label": {"type": "plain_text", "text": section_label},
            "element": {
                "type": "checkboxes",
                "action_id": "selected_items",
                "options": options,
                "initial_options": options,  # 기본: 전체 선택
            },
        })

    blocks.append({
        "type": "input",
        "block_id": "additional_request",
        "optional": True,
        "label": {"type": "plain_text", "text": "추가 요구사항 (선택)"},
        "element": {
            "type": "plain_text_input",
            "action_id": "request_text",
            "multiline": True,
            "placeholder": {"type": "plain_text", "text": "예: 인증 관련 항목을 더 강조해주세요"},
        },
    })

    return blocks


async def _execute_pipeline(
    subcommand: str,
    user_message: str,
    user: str,
    channel: str,
    say,
) -> None:
    """세션 관리 없이 inspector → issue_gen 파이프라인만 실행한다."""
    await say(f"<@{user}> 코드베이스를 분석 중입니다...")
    inspector_result = await OpenAiAgentFactory.file_tree_insepctor().run(user_message)
    logger.info("slash | inspector done | user=%s subcommand=%s", user, subcommand)

    await say(f"<@{user}> 이슈를 생성 중입니다...")
    issue_result = await _issue_agent(subcommand).run(inspector_result.output)
    logger.info("slash | issue_gen done | user=%s", user)

    _pending[(channel, user)] = _IssueContext(
        subcommand=subcommand,
        user_message=user_message,
        inspector_output=inspector_result.output,
        typed_output=issue_result.typed_output,
    )
    formatted = issue_result.typed_output.slack_format()
    await say(blocks=build_issue_blocks(user, formatted, issue_result.usage.format()))


async def _run_issue_pipeline(
    subcommand: str,
    user_message: str,
    user: str,
    channel: str,
    session_manager: ISessionManager,
    say,
) -> None:
    """세션을 획득한 뒤 파이프라인을 실행한다."""
    session_key = f"{channel}:{user}"
    if not await session_manager.try_acquire(session_key):
        await say(f"<@{user}> 이미 처리 중인 요청이 있습니다.")
        return

    try:
        await _execute_pipeline(subcommand, user_message, user, channel, say)
    except Exception:
        logger.exception("slash | user=%s 처리 중 오류 발생", user)
        await say(f"<@{user}> 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        await session_manager.release(session_key)


def register(app: AsyncApp, session_manager: ISessionManager) -> None:
    """slash command 및 버튼 액션 핸들러를 등록한다."""

    def _modal_view(callback_id: str, title: str, blocks: list[dict], metadata: str) -> dict:
        return {
            "type": "modal",
            "callback_id": callback_id,
            "private_metadata": metadata,
            "title": {"type": "plain_text", "text": title},
            "submit": {"type": "plain_text", "text": "생성"},
            "close": {"type": "plain_text", "text": "취소"},
            "blocks": blocks,
        }

    @app.command("/feat")
    async def handle_feat(ack, command: dict, client) -> None:
        await ack()
        user: str = command.get("user_id", "unknown")
        channel: str = command.get("channel_id", "unknown")
        trigger_id: str = command["trigger_id"]
        await client.views_open(
            trigger_id=trigger_id,
            view=_modal_view(FeatModalInput.CALLBACK_ID, "기능 요청", FeatModalInput.modal_blocks(), f"{channel}:{user}"),
        )

    @app.view(FeatModalInput.CALLBACK_ID)
    async def handle_feat_submit(ack, body, client) -> None:
        await ack()
        metadata: str = body["view"]["private_metadata"]
        channel, user = metadata.split(":", 1)
        values: dict = body["view"]["state"]["values"]
        modal_input = FeatModalInput.from_view(values)
        await client.chat_postMessage(channel=channel, text=f"<@{user}> 요청을 접수했습니다. 잠시 후 결과를 전달드릴게요.")
        await _run_issue_pipeline("feat", modal_input.to_prompt(), user, channel, session_manager,
                                  lambda *args, **kwargs: client.chat_postMessage(channel=channel, **({'text': args[0]} if args else {}), **kwargs))

    @app.command("/refactor")
    async def handle_refactor(ack, command: dict, client) -> None:
        await ack()
        user: str = command.get("user_id", "unknown")
        channel: str = command.get("channel_id", "unknown")
        trigger_id: str = command["trigger_id"]
        await client.views_open(
            trigger_id=trigger_id,
            view=_modal_view(RefactorModalInput.CALLBACK_ID, "리팩토링 요청", RefactorModalInput.modal_blocks(), f"{channel}:{user}"),
        )

    @app.view(RefactorModalInput.CALLBACK_ID)
    async def handle_refactor_submit(ack, body, client) -> None:
        await ack()
        metadata: str = body["view"]["private_metadata"]
        channel, user = metadata.split(":", 1)
        values: dict = body["view"]["state"]["values"]
        modal_input = RefactorModalInput.from_view(values)
        await client.chat_postMessage(channel=channel, text=f"<@{user}> 요청을 접수했습니다. 잠시 후 결과를 전달드릴게요.")
        await _run_issue_pipeline("refactor", modal_input.to_prompt(), user, channel, session_manager,
                                  lambda *args, **kwargs: client.chat_postMessage(channel=channel, **({'text': args[0]} if args else {}), **kwargs))

    @app.command("/fix")
    async def handle_fix(ack, command: dict, client) -> None:
        await ack()
        user: str = command.get("user_id", "unknown")
        channel: str = command.get("channel_id", "unknown")
        trigger_id: str = command["trigger_id"]
        await client.views_open(
            trigger_id=trigger_id,
            view=_modal_view(FixModalInput.CALLBACK_ID, "버그 수정 요청", FixModalInput.modal_blocks(), f"{channel}:{user}"),
        )

    @app.view(FixModalInput.CALLBACK_ID)
    async def handle_fix_submit(ack, body, client) -> None:
        await ack()
        metadata: str = body["view"]["private_metadata"]
        channel, user = metadata.split(":", 1)
        values: dict = body["view"]["state"]["values"]
        modal_input = FixModalInput.from_view(values)
        await client.chat_postMessage(channel=channel, text=f"<@{user}> 요청을 접수했습니다. 잠시 후 결과를 전달드릴게요.")
        await _run_issue_pipeline("fix", modal_input.to_prompt(), user, channel, session_manager,
                                  lambda *args, **kwargs: client.chat_postMessage(channel=channel, **({'text': args[0]} if args else {}), **kwargs))

    @app.action("issue_accept")
    async def handle_accept(ack, body, say) -> None:
        await ack()
        user: str = body["user"]["id"]
        channel: str = body["channel"]["id"]
        _pending.pop((channel, user), None)
        await session_manager.release(f"{channel}:{user}")
        await say(f"<@{user}> 이슈가 수락되었습니다.")
        logger.info("slash | issue accepted | user=%s", user)

    @app.action("issue_reject")
    async def handle_reject(ack, body, client) -> None:
        """현재 이슈 항목을 체크박스 Modal로 표시해 제외할 항목을 선택받는다."""
        await ack()
        user: str = body["user"]["id"]
        channel: str = body["channel"]["id"]
        trigger_id: str = body["trigger_id"]

        ctx = _pending.get((channel, user))
        if not ctx:
            await client.chat_postMessage(
                channel=channel,
                text=f"<@{user}> 재요청할 이슈 컨텍스트가 없습니다. 명령어를 다시 입력해주세요.",
            )
            return

        droppable = ctx.typed_output.droppable_items()
        await client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "issue_reject_modal",
                "private_metadata": f"{channel}:{user}",
                "title": {"type": "plain_text", "text": "이슈 재요청"},
                "submit": {"type": "plain_text", "text": "재생성"},
                "close": {"type": "plain_text", "text": "취소"},
                "blocks": _build_reject_modal_blocks(droppable),
            },
        )

    @app.view("issue_reject_modal")
    async def handle_reject_modal(ack, body, client) -> None:
        """Modal 제출 시 체크 해제된 항목을 제외하고 이슈를 재생성한다."""
        await ack()

        metadata: str = body["view"]["private_metadata"]
        channel, user = metadata.split(":", 1)

        ctx = _pending.get((channel, user))
        if not ctx:
            return

        # 선택된(체크된) 항목 수집
        values: dict = body["view"]["state"]["values"]
        selected_ids: set[str] = set()
        for block_id, block_val in values.items():
            if block_id.startswith("drop_"):
                selected_opts = block_val.get("selected_items", {}).get("selected_options") or []
                for opt in selected_opts:
                    selected_ids.add(opt["value"])

        additional_request: str = (
            values.get("additional_request", {})
            .get("request_text", {})
            .get("value") or ""
        )

        # 체크 해제된 항목 ID = 제외할 항목
        all_ids = {item.id for item in ctx.typed_output.droppable_items()}
        dropped_ids = all_ids - selected_ids

        # 추가 요건도 없고 제외 항목도 없으면 아무 변경 없음 → LLM 호출 생략
        if not dropped_ids and not additional_request:
            await client.chat_postMessage(channel=channel, text=f"<@{user}> 변경 사항이 없습니다.")
            return

        # 코드 레벨에서 제외 항목 제거 → 필터링된 draft 생성
        filtered = ctx.typed_output.without(dropped_ids)
        draft_text = filtered.slack_format()

        # [Inspector Context] + [Current Issue Draft] + 추가 요건
        reissue_input = f"[Inspector Context]\n{ctx.inspector_output}\n\n[Current Issue Draft]\n{draft_text}"
        if additional_request:
            reissue_input += f"\n\n---\nAdditional requirements: {additional_request}"

        await client.chat_postMessage(channel=channel, text=f"<@{user}> 이슈를 재생성 중입니다...")
        logger.info("slash | reject modal submitted | user=%s dropped=%d", user, len(dropped_ids))

        try:
            issue_result = await _reissue_agent(ctx.subcommand).run(reissue_input)
            _pending[(channel, user)] = _IssueContext(
                subcommand=ctx.subcommand,
                user_message=ctx.user_message,
                inspector_output=ctx.inspector_output,
                typed_output=issue_result.typed_output,
            )
            formatted = issue_result.typed_output.slack_format()
            await client.chat_postMessage(
                channel=channel,
                blocks=build_issue_blocks(user, formatted, issue_result.usage.format()),
            )
        except Exception:
            logger.exception("slash | reject modal | user=%s 오류 발생", user)
            await client.chat_postMessage(
                channel=channel,
                text=f"<@{user}> 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            )

    @app.action("issue_drop")
    async def handle_drop(ack, body, say) -> None:
        """inspector부터 처음부터 다시 실행한다."""
        await ack()
        user: str = body["user"]["id"]
        channel: str = body["channel"]["id"]

        ctx = _pending.get((channel, user))
        if not ctx:
            await say(f"<@{user}> 재실행할 컨텍스트가 없습니다. 명령어를 다시 입력해주세요.")
            return

        await say(f"<@{user}> 코드베이스 탐색부터 다시 시작합니다...")
        try:
            await _execute_pipeline(ctx.subcommand, ctx.user_message, user, channel, say)
            logger.info("slash | issue dropped and restarted | user=%s", user)

        except Exception:
            logger.exception("slash | drop | user=%s 오류 발생", user)
            await say(f"<@{user}> 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
