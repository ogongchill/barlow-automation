"""Worker Lambda 진입점 — step_worker_handler로 위임한다."""

from src.app.handlers.step_worker_handler import handler  # noqa: F401
