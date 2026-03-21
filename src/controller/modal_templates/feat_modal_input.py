from typing import ClassVar
from pydantic import BaseModel
from src.controller.modal_templates import _ModalField, _parse_bullets


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
