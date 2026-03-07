"""
모델 정보 중앙 레지스트리.
usage.py와 runner들은 이 파일에서 pricing / 기본 모델을 가져온다.

Claude 출처: https://docs.anthropic.com/en/docs/about-claude/models
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    name: str
    input_price: float   # USD per million input tokens
    output_price: float  # USD per million output tokens


class Model:
    class Claude:
        # --- Latest ---
        OPUS_4_6 = ModelConfig("anthropic", "claude-opus-4-6",            5.00, 25.00)
        SONNET_4_6 = ModelConfig("anthropic", "claude-sonnet-4-6",         3.00, 15.00)
        HAIKU_4_5 = ModelConfig("anthropic", "claude-haiku-4-5-20251001",  1.00,  5.00)

        # --- Legacy ---
        OPUS_4_5 = ModelConfig("anthropic", "claude-opus-4-5-20251101",   5.00, 25.00)
        SONNET_4_5 = ModelConfig("anthropic", "claude-sonnet-4-5-20250929", 3.00, 15.00)
        OPUS_4_1 = ModelConfig("anthropic", "claude-opus-4-1-20250805",   15.00, 75.00)
        SONNET_4_0 = ModelConfig("anthropic", "claude-sonnet-4-20250514",   3.00, 15.00)
        OPUS_4_0 = ModelConfig("anthropic", "claude-opus-4-20250514",     15.00, 75.00)
        HAIKU_3 = ModelConfig("anthropic", "claude-3-haiku-20240307",      0.25,  1.25)

        DEFAULT = SONNET_4_6

    class GPT:
        CODEX_5_3 = ModelConfig("openai", "gpt-5.3-codex",      1.75, 14.00)
        GPT_5_4 = ModelConfig("openai", "gpt-5.4",              2.50, 15.00)
        GPT_5_2 = ModelConfig("openai", "gpt-5.2",              1.75, 14.00)


        DEFAULT = GPT_5_4


# ---------------------------------------------------------------------------
# 조회 헬퍼
# ---------------------------------------------------------------------------

_CLAUDE_ALL = [
    Model.Claude.OPUS_4_6,
    Model.Claude.SONNET_4_6,
    Model.Claude.HAIKU_4_5,
    Model.Claude.OPUS_4_5,
    Model.Claude.SONNET_4_5,
    Model.Claude.OPUS_4_1,
    Model.Claude.SONNET_4_0,
    Model.Claude.OPUS_4_0,
    Model.Claude.HAIKU_3,
]

_GPT_ALL = [
    Model.GPT.CODEX_5_3,
    Model.GPT.GPT_5_4,
]

_REGISTRY: dict[str, ModelConfig] = {m.name: m for m in _CLAUDE_ALL + _GPT_ALL}


def get(model_name: str) -> ModelConfig | None:
    """모델 이름으로 ModelConfig 조회. 없으면 None."""
    return _REGISTRY.get(model_name)


def pricing(model_name: str) -> tuple[float, float]:
    """(input_usd_per_mtok, output_usd_per_mtok). 미등록 모델은 prefix 매칭 후 DEFAULT 적용."""
    if model_name in _REGISTRY:
        m = _REGISTRY[model_name]
        return m.input_price, m.output_price

    # prefix 매칭 (스냅샷 suffix 포함 모델명 대응)
    for m in _CLAUDE_ALL + _GPT_ALL:
        if model_name.startswith(m.name.split("-2025")[0].split("-2024")[0]):
            return m.input_price, m.output_price

    return Model.Claude.DEFAULT.input_price, Model.Claude.DEFAULT.output_price
