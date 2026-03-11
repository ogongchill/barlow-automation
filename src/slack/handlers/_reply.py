"""핸들러 공통 응답 포맷 유틸리티."""


def build_reply(user: str | None, response: str, usage_text: str) -> str:
    """사용자 멘션과 usage 정보를 포함한 응답 문자열을 생성한다."""
    base = f"<@{user}> {response}" if user else response
    if not usage_text:
        return base
    return f"{base}\n\n```{usage_text}```"


_SECTION_LIMIT = 2900  # Slack section block text 한도(3000)보다 여유있게


def _section_blocks(text: str) -> list[dict]:
    """3000자 제한을 고려해 텍스트를 여러 section 블록으로 분할한다."""
    chunks = [text[i:i + _SECTION_LIMIT] for i in range(0, len(text), _SECTION_LIMIT)]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": chunk}} for chunk in chunks]


def build_issue_blocks(user: str | None, response: str, usage_text: str) -> list[dict]:
    """이슈 생성 결과를 수락/재요청 버튼과 함께 Block Kit 형태로 반환한다."""
    mention = f"<@{user}>\n" if user else ""
    blocks: list[dict] = _section_blocks(f"{mention}{response}")

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
