"""Slash command 입력 폼 스키마 및 Slack Modal 블록 생성."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel


@dataclass(frozen=True)
class _ModalField:
    """Slack input block 단일 필드 설정."""
    block_id: str
    label: str
    placeholder: str
    required: bool = True
    multiline: bool = False

    def to_block(self) -> dict:
        return {
            "type": "input",
            "block_id": self.block_id,
            "optional": not self.required,
            "label": {"type": "plain_text", "text": self.label},
            "element": {
                "type": "plain_text_input",
                "action_id": "input",
                "multiline": self.multiline,
                "placeholder": {"type": "plain_text", "text": self.placeholder},
            },
        }


def _parse_bullets(raw: str) -> list[str]:
    """줄바꿈 구분 텍스트를 항목 리스트로 정규화한다."""
    result = []
    for line in raw.splitlines():
        stripped = line.strip().lstrip("-•").strip()
        if stripped:
            result.append(stripped)
    return result


class FeatModalInput(BaseModel):
    """
    /feat 슬래시 커맨드 입력 폼 스키마.

    [feat] {기능 이름}

    배경: {왜 필요한가 — 1~2줄}

    기능:
    - {어떤 행위가 가능해야 하는가 — 주어+동사 형태}

    제약:
    - {누가 사용 가능한가, 비즈니스 제약 조건}

    설계 요구사항: (선택)
    - {API 경로, 응답 필드 등}
    """

    CALLBACK_ID: ClassVar[str] = "feat_submit"

    _FIELDS: ClassVar[list[_ModalField]] = [
        _ModalField(
            "feature_name",
            "기능 이름",
            "예: 즐겨찾기 기능",
        ),
        _ModalField(
            "background",
            "배경",
            "왜 이 기능이 필요한가요? (1~2줄)",
            multiline=True,
        ),
        _ModalField(
            "features",
            "기능 목록",
            "어떤 행위가 가능해야 하는가 (줄바꿈으로 구분, 주어+동사 형태)",
            multiline=True,
        ),
        _ModalField(
            "constraints",
            "제약 조건",
            "누가 사용 가능한가, 비즈니스 제약 조건 (줄바꿈으로 구분)",
            multiline=True,
        ),
        _ModalField(
            "design_requirements",
            "설계 요구사항",
            "API 경로, 응답 필드 등 — 선택 사항",
            required=False,
            multiline=True,
        ),
    ]

    feature_name: str
    background: str
    features: str
    constraints: str
    design_requirements: str = ""

    @classmethod
    def modal_blocks(cls) -> list[dict]:
        """Slack Modal input 블록 목록을 반환한다."""
        return [field.to_block() for field in cls._FIELDS]

    @classmethod
    def from_view(cls, values: dict) -> "FeatModalInput":
        """view_submission state.values를 파싱해 인스턴스를 생성한다."""
        def get(block_id: str) -> str:
            return values.get(block_id, {}).get("input", {}).get("value") or ""

        return cls(
            feature_name=get("feature_name"),
            background=get("background"),
            features=get("features"),
            constraints=get("constraints"),
            design_requirements=get("design_requirements"),
        )

    def to_prompt(self) -> str:
        """파이프라인 user_message 형식으로 직렬화한다."""
        lines = [
            f"[feat] {self.feature_name}",
            "",
            f"배경: {self.background}",
            "",
            "기능:",
            *[f"- {item}" for item in _parse_bullets(self.features)],
            "",
            "제약:",
            *[f"- {item}" for item in _parse_bullets(self.constraints)],
        ]
        if self.design_requirements.strip():
            lines += [
                "",
                "설계 요구사항:",
                *[f"- {item}" for item in _parse_bullets(self.design_requirements)],
            ]
        return "\n".join(lines)


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


class FixModalInput(BaseModel):
    """
    /fix 슬래시 커맨드 입력 폼 스키마.

    [fix] {버그 제목}

    증상: {어떤 문제가 발생하는가 — 1~2줄}

    재현 조건:
    - {언제, 어떤 조건에서 발생하는가}

    예상 동작: {정상적으로 동작해야 하는 방식}

    관련 영역: (선택)
    - {의심되는 모듈, 클래스, API 경로}
    """

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
