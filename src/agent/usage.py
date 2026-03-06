"""
Per-request token usage tracking with per-model cost estimation.
"""

from dataclasses import dataclass, field

# USD per million tokens  {model_prefix: (input, output)}
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (base_input_tokens_usd_per_mtok, output_tokens_usd_per_mtok)
    "claude-opus-4.6": (5.00, 25.00),
    "claude-opus-4.5": (5.00, 25.00),

    "claude-opus-4.1": (15.00, 75.00),
    "claude-opus-4":   (15.00, 75.00),
    "claude-opus-3":   (15.00, 75.00),  # deprecated

    "claude-sonnet-4.6": (3.00, 15.00),
    "claude-sonnet-4.5": (3.00, 15.00),
    "claude-sonnet-4":   (3.00, 15.00),
    "claude-sonnet-3.7": (3.00, 15.00),  # deprecated

    "claude-haiku-4.5": (1.00, 5.00),
    "claude-haiku-3.5": (0.80, 4.00),
    "claude-haiku-3":   (0.25, 1.25),
}

_DEFAULT_PRICING = _MODEL_PRICING["claude-sonnet-4.6"]


def _get_pricing(model: str) -> tuple[float, float]:
    for prefix, pricing in _MODEL_PRICING.items():
        if model.startswith(prefix):
            return pricing
    return _DEFAULT_PRICING


@dataclass
class ModelUsage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        input_price, output_price = _get_pricing(self.model)
        return (
            self.input_tokens / 1_000_000 * input_price
            + self.output_tokens / 1_000_000 * output_price
        )

    def format(self) -> str:
        return (
            f"{self.model:<30} "
            f"in {self.input_tokens:>7,}  out {self.output_tokens:>7,}  "
            f"~${self.cost_usd:.5f}"
        )


@dataclass
class RequestUsage:
    _by_model: dict[str, ModelUsage] = field(default_factory=dict)
    _actual_cost_usd: float | None = None  # ResultMessage.total_cost_usd (API 실측값)

    def set_result(self, model: str, usage: dict, total_cost_usd: float | None) -> None:
        """ResultMessage 수신 시 호출. usage는 API 반환 dict."""
        if model not in self._by_model:
            self._by_model[model] = ModelUsage(model=model)
        entry = self._by_model[model]
        entry.input_tokens = usage.get("input_tokens", 0) or 0
        entry.output_tokens = usage.get("output_tokens", 0) or 0
        self._actual_cost_usd = total_cost_usd

    @property
    def total_input(self) -> int:
        return sum(m.input_tokens for m in self._by_model.values())

    @property
    def total_output(self) -> int:
        return sum(m.output_tokens for m in self._by_model.values())

    @property
    def total_cost(self) -> float:
        # API 실측값 우선, 없으면 pricing 테이블로 추정
        if self._actual_cost_usd is not None:
            return self._actual_cost_usd
        return sum(m.cost_usd for m in self._by_model.values())

    def format(self) -> str:
        if not self._by_model:
            return ""
        cost_label = "$" if self._actual_cost_usd is not None else "~$"
        lines = ["model                          input      output    cost"]
        lines.append("-" * 60)
        for entry in self._by_model.values():
            lines.append(entry.format())
        if len(self._by_model) > 1:
            lines.append("-" * 60)
        lines.append(
            f"{'total':<30} "
            f"in {self.total_input:>7,}  out {self.total_output:>7,}  "
            f"{cost_label}{self.total_cost:.5f}"
        )
        return "\n".join(lines)
