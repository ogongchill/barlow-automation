"""이벤트 타입별 핸들러 라우팅 -- app.py는 이 모듈만 호출한다."""

from slack_bolt.async_app import AsyncApp

from src.session.manager import ISessionManager
from src.slack.handlers import mention_handler, message_handler, slash_handler


def register_routes(
    app: AsyncApp,
    session_manager: ISessionManager,
) -> None:
    """모든 Slack 이벤트/커맨드 핸들러를 app에 등록한다."""
    mention_handler.register(app, session_manager)
    slash_handler.register(app, session_manager)
    message_handler.register(app, session_manager)
