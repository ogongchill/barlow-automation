"""
Per-request token usage tracking with per-model cost estimation.
"""

from dataclasses import dataclass, field

from src.agent.runner.models import pricing as _get_pricing


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
