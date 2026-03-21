from typing import ClassVar
from pydantic import BaseModel
from src.controller.modal_templates import _ModalField, _parse_bullets


class RefactorModalInput(BaseModel):
    """
    /refactor 슬래시 커맨드 입력 폼 스키마.

    [refactor] {대상 이름}

    배경: {왜 리팩토링이 필요한가 — 1~2줄}

    AS-IS:
    - {현재 문제점}

    TO-BE:
    - {개선 목표}

    제약: (선택)
    - {보존해야 할 비즈니스 규칙, 아키텍처 제약}
    """

    CALLBACK_ID: ClassVar[str] = "refactor_submit"

    _FIELDS: ClassVar[list[_ModalField]] = [
        _ModalField(
            "target_name",
            "리팩토링 대상",
            "예: SessionManager 인터페이스 분리",
        ),
        _ModalField(
            "background",
            "배경",
            "왜 리팩토링이 필요한가요? (1~2줄)",
            multiline=True,
        ),
        _ModalField(
            "as_is",
            "AS-IS (현재 문제점)",
            "현재 어떤 문제가 있는가 (줄바꿈으로 구분)",
            multiline=True,
        ),
        _ModalField(
            "to_be",
            "TO-BE (개선 목표)",
            "어떻게 개선되어야 하는가 (줄바꿈으로 구분)",
            multiline=True,
        ),
        _ModalField(
            "constraints",
            "제약 조건",
            "보존해야 할 비즈니스 규칙, 아키텍처 제약 — 선택 사항",
            required=False,
            multiline=True,
        ),
    ]

    target_name: str
    background: str
    as_is: str
    to_be: str
    constraints: str = ""

    @classmethod
    def modal_blocks(cls) -> list[dict]:
        """Slack Modal input 블록 목록을 반환한다."""
        return [field.to_block() for field in cls._FIELDS]

    @classmethod
    def from_view(cls, values: dict) -> "RefactorModalInput":
        """view_submission state.values를 파싱해 인스턴스를 생성한다."""
        def get(block_id: str) -> str:
            return values.get(block_id, {}).get("input", {}).get("value") or ""

        return cls(
            target_name=get("target_name"),
            background=get("background"),
            as_is=get("as_is"),
            to_be=get("to_be"),
            constraints=get("constraints"),
        )

    def to_prompt(self) -> str:
        """파이프라인 user_message 형식으로 직렬화한다."""
        lines = [
            f"[refactor] {self.target_name}",
            "",
            f"배경: {self.background}",
            "",
            "AS-IS:",
            *[f"- {item}" for item in _parse_bullets(self.as_is)],
            "",
            "TO-BE:",
            *[f"- {item}" for item in _parse_bullets(self.to_be)],
        ]
        if self.constraints.strip():
            lines += [
                "",
                "제약:",
                *[f"- {item}" for item in _parse_bullets(self.constraints)],
            ]
        return "\n".join(lines)
