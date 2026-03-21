from typing import ClassVar
from pydantic import BaseModel
from src.controller.modal_templates import _ModalField, _parse_bullets

class FixModalInput(BaseModel):

    CALLBACK_ID: ClassVar[str] = "fix_submit"

    _FIELDS: ClassVar[list[_ModalField]] = [
        _ModalField(
            "bug_title",
            "버그 제목",
            "예: 로그인 시 NPE 발생",
        ),
        _ModalField(
            "symptom",
            "증상",
            "어떤 문제가 발생하는가 (1~2줄)",
            multiline=True,
        ),
        _ModalField(
            "reproduction",
            "재현 조건",
            "언제, 어떤 조건에서 발생하는가 (줄바꿈으로 구분)",
            multiline=True,
        ),
        _ModalField(
            "expected",
            "예상 동작",
            "정상적으로 동작해야 하는 방식",
            multiline=True,
        ),
        _ModalField(
            "related_areas",
            "관련 영역",
            "의심되는 모듈, 클래스, API 경로 — 선택 사항",
            required=False,
            multiline=True,
        ),
    ]

    bug_title: str
    symptom: str
    reproduction: str
    expected: str
    related_areas: str = ""

    @classmethod
    def modal_blocks(cls) -> list[dict]:
        """Slack Modal input 블록 목록을 반환한다."""
        return [field.to_block() for field in cls._FIELDS]

    @classmethod
    def from_view(cls, values: dict) -> "FixModalInput":
        """view_submission state.values를 파싱해 인스턴스를 생성한다."""
        def get(block_id: str) -> str:
            return values.get(block_id, {}).get("input", {}).get("value") or ""

        return cls(
            bug_title=get("bug_title"),
            symptom=get("symptom"),
            reproduction=get("reproduction"),
            expected=get("expected"),
            related_areas=get("related_areas"),
        )

    def to_prompt(self) -> str:
        """파이프라인 user_message 형식으로 직렬화한다."""
        lines = [
            f"[fix] {self.bug_title}",
            "",
            f"증상: {self.symptom}",
            "",
            "재현 조건:",
            *[f"- {item}" for item in _parse_bullets(self.reproduction)],
            "",
            f"예상 동작: {self.expected}",
        ]
        if self.related_areas.strip():
            lines += [
                "",
                "관련 영역:",
                *[f"- {item}" for item in _parse_bullets(self.related_areas)],
            ]
        return "\n".join(lines)
