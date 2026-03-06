"""핸들러 공통 응답 포맷 유틸리티."""


def build_reply(user: str | None, response: str, usage_text: str) -> str:
    """사용자 멘션과 usage 정보를 포함한 응답 문자열을 생성한다."""
    base = f"<@{user}> {response}" if user else response
    if not usage_text:
        return base
    return f"{base}\n\n```{usage_text}```"
