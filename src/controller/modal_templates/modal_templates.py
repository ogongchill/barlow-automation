"""Slash command 입력 폼 스키마 및 Slack Modal 블록 생성."""

from __future__ import annotations
from dataclasses import dataclass


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
