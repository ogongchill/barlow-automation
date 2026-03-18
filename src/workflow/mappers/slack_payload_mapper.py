"""Slack Block Kit 응답 빌더 및 이슈 포맷터 -- _reply.py에서 이동/확장."""

import json
from functools import singledispatch

from src.domain.issue.entities import (
    BaseIssueTemplate,
    FeatTemplate,
    RefactorTemplate,
    FixTemplate,
)


# -- 이슈 Slack 포맷터 --------------------------------------------------------

def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {item}" for item in items)


@singledispatch
def slack_format(template: BaseIssueTemplate) -> str:
    """이슈 템플릿을 Slack mrkdwn 형식 문자열로 변환한다."""
    raise NotImplementedError(f"slack_format not implemented for {type(template)}")


@slack_format.register
def _(template: FeatTemplate) -> str:
    parts = [
        f"*{template.issue_title}*",
        template.about,
        f"*목표*\n{template.goal}" if template.goal else None,
        f"*신규 기능*\n{_bullets(template.new_features)}",
        f"*도메인 규칙*\n{_bullets(template.domain_rules)}",
        f"*추가정보*\n{template.additional_info}" if template.additional_info else None,
    ]
    return "\n\n".join(p for p in parts if p is not None)


@slack_format.register
def _(template: RefactorTemplate) -> str:
    goal_lines = []
    for i, goal in enumerate(template.goals, start=1):
        goal_lines.append(
            f"*목표 {i}*\n_AS-IS_\n{_bullets(goal.as_is)}\n_TO-BE_\n{_bullets(goal.to_be)}"
        )
    return "\n\n".join([
        f"*{template.issue_title}*",
        template.about,
        *goal_lines,
        f"*도메인 규칙*\n{_bullets(template.domain_rules)}",
        f"*기술 제약*\n{_bullets(template.domain_constraints)}",
    ])


@slack_format.register
def _(template: FixTemplate) -> str:
    problem_lines = "\n".join(
        f"• *문제:* {p.issue}\n  *제안:* {p.suggestion}"
        for p in template.problems
    )
    impl_lines = "\n".join(f"{s.step}. {s.todo}" for s in template.implementation)
    return "\n\n".join([
        f"*{template.issue_title}*",
        template.about,
        f"*문제 및 해결 방안*\n{problem_lines}",
        f"*구현 단계*\n{impl_lines}",
        f"*도메인 규칙*\n{_bullets(template.domain_rules)}",
        f"*기술 제약*\n{_bullets(template.domain_constraints)}",
    ])


# -- Block Kit 빌더 -----------------------------------------------------------

def build_reply(user: str | None, response: str, usage_text: str) -> str:
    """사용자 멘션과 usage 정보를 포함한 응답 문자열을 생성한다."""
    base = f"<@{user}> {response}" if user else response
    if not usage_text:
        return base
    return f"{base}\n\n```{usage_text}```"


_SECTION_LIMIT = 2900


def _section_blocks(text: str) -> list[dict]:
    """3000자 제한을 고려해 텍스트를 여러 section 블록으로 분할한다."""
    chunks = [text[i:i + _SECTION_LIMIT] for i in range(0, len(text), _SECTION_LIMIT)]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": chunk}} for chunk in chunks]


def build_issue_blocks(user: str | None, template: BaseIssueTemplate, usage_text: str, workflow_id: str = "") -> list[dict]:
    """이슈 생성 결과를 수락/재요청 버튼과 함께 Block Kit 형태로 반환한다."""
    mention = f"<@{user}>\n" if user else ""
    blocks: list[dict] = _section_blocks(f"{mention}{slack_format(template)}")

    if usage_text:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"```{usage_text}```"}],
        })
    buttons: list[dict] = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "수락"},
            "style": "primary",
            "action_id": "issue_accept",
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "재요청"},
            "action_id": "issue_reject",
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "드롭 후 재탐색"},
            "style": "danger",
            "action_id": "issue_drop",
        },
    ]
    if workflow_id:
        for btn in buttons:
            btn["value"] = workflow_id
    blocks.append({"type": "actions", "elements": buttons})
    return blocks


def build_reject_modal(message_ts: str = "", channel_id: str = "", user_id: str = "", *, workflow_id: str = "") -> dict:
    """재요청 추가 요구사항 입력 Modal을 반환한다."""
    return {
        "type": "modal",
        "callback_id": "reject_submit",
        "private_metadata": json.dumps({
            **({"workflow_id": workflow_id} if workflow_id else {"message_ts": message_ts}),
            "channel_id": channel_id, "user_id": user_id,
        }),
        "title": {"type": "plain_text", "text": "재요청"},
        "submit": {"type": "plain_text", "text": "제출"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": "additional_requirements",
                "optional": True,
                "label": {"type": "plain_text", "text": "추가 요구사항"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "수정 또는 추가할 내용을 입력하세요 (선택)"},
                },
            }
        ],
    }


def build_drop_modal(message_ts: str = "", channel_id: str = "", user_id: str = "", items: list | None = None, *, workflow_id: str = "") -> dict:
    """드롭할 항목 선택 Modal을 반환한다."""
    options = [
        {"text": {"type": "mrkdwn", "text": f"*{item.section}* {item.text}"}, "value": item.id}
        for item in (items or [])
    ]
    return {
        "type": "modal",
        "callback_id": "drop_submit",
        "private_metadata": json.dumps({
            **({"workflow_id": workflow_id} if workflow_id else {"message_ts": message_ts}),
            "channel_id": channel_id, "user_id": user_id,
        }),
        "title": {"type": "plain_text", "text": "드롭 후 재탐색"},
        "submit": {"type": "plain_text", "text": "재탐색"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": "drop_selection",
                "optional": True,
                "label": {"type": "plain_text", "text": "제거할 항목을 선택하세요"},
                "element": {
                    "type": "checkboxes",
                    "action_id": "items",
                    "options": options,
                },
            }
        ],
    }


# -- BC 판단 결과 블록 (신규) ---------------------------------------------------

def build_bc_decision_blocks(user: str | None, bc_decision_json: str, usage_text: str) -> list[dict]:
    """BC 판단 결과를 수락/거부 버튼과 함께 Block Kit 형태로 반환한다."""
    bc = json.loads(bc_decision_json)
    mention = f"<@{user}>\n" if user else ""

    lines = [
        f"{mention}*BC 판단 결과*",
        f"*결정*: {'기존 BC 재사용' if bc.get('decision') == 'reuse_existing' else '신규 BC 제안'}",
        f"*주요 컨텍스트*: {bc.get('primary_context', '')}",
        f"*근거*: {bc.get('mapping_summary', '')}",
    ]

    contexts = bc.get("selected_contexts", [])
    if contexts:
        ctx_lines = [f"• {c['name']} ({c.get('type','')}, {c.get('confidence',0):.2f}) — {c.get('reason','')}" for c in contexts]
        lines.append("*선택된 컨텍스트*\n" + "\n".join(ctx_lines))

    validation = bc.get("validation_points", [])
    if validation:
        lines.append("*검증 포인트*\n" + "\n".join(f"• {v}" for v in validation))

    text = "\n\n".join(lines)
    blocks = _section_blocks(text)

    if usage_text:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"```{usage_text}```"}]})

    blocks.append({
        "type": "actions",
        "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "BC 수락"}, "style": "primary", "action_id": "bc_accept"},
            {"type": "button", "text": {"type": "plain_text", "text": "BC 거부"}, "action_id": "bc_reject"},
        ],
    })
    return blocks


def build_bc_reject_modal(message_ts: str, channel_id: str, user_id: str) -> dict:
    """BC 거부 사유 입력 Modal을 반환한다."""
    return {
        "type": "modal",
        "callback_id": "bc_reject_submit",
        "private_metadata": json.dumps({"message_ts": message_ts, "channel_id": channel_id, "user_id": user_id}),
        "title": {"type": "plain_text", "text": "BC 거부"},
        "submit": {"type": "plain_text", "text": "제출"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [{
            "type": "input",
            "block_id": "feedback",
            "optional": True,
            "label": {"type": "plain_text", "text": "BC 판단에 대한 의견"},
            "element": {"type": "plain_text_input", "action_id": "input", "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "왜 이 BC가 맞지 않는지 입력하세요 (선택)"}},
        }],
    }
