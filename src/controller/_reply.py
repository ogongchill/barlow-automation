"""Slack Block Kit 응답 빌더 및 이슈 포맷터."""

from functools import singledispatch

from src.domain.issue_templates import (
    BaseIssueTemplate,
    FeatTemplate,
    RefactorTemplate,
    FixTemplate,
)


# ── 이슈 Slack 포맷터 ────────────────────────────────────────────────────────

def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {item}" for item in items)


@singledispatch
def slack_format(template: BaseIssueTemplate) -> str:
    """이슈 템플릿을 Slack mrkdwn 형식 문자열로 변환한다."""
    raise NotImplementedError(f"slack_format not implemented for {type(template)}")


@slack_format.register
def _(template: FeatTemplate) -> str:
    return "\n\n".join([
        f"*{template.issue_title}*",
        template.about,
        f"*신규 기능*\n{_bullets(template.new_features)}",
        f"*도메인 규칙*\n{_bullets(template.domain_rules)}",
        f"*기술 제약*\n{_bullets(template.domain_constraints)}",
    ])


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


# ── Block Kit 빌더 ───────────────────────────────────────────────────────────

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


def build_issue_blocks(user: str | None, template: BaseIssueTemplate, usage_text: str) -> list[dict]:
    """이슈 생성 결과를 수락/재요청 버튼과 함께 Block Kit 형태로 반환한다."""
    mention = f"<@{user}>\n" if user else ""
    blocks: list[dict] = _section_blocks(f"{mention}{slack_format(template)}")

    if usage_text:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"```{usage_text}```"}],
        })
    blocks.append({
        "type": "actions",
        "elements": [
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
        ],
    })
    return blocks
