"""
Per-request token usage tracking with per-model cost estimation.
"""

from dataclasses import dataclass, field

from src.agent.runner.models import pricing as _get_pricing

from dataclasses import dataclass, field

from src.agent.runner.models import pricing as get_pricing


@dataclass(slots=True)
class TurnUsage:
    """단일 LLM 호출(turn)의 토큰 사용량. agent 및 모델 정보 포함."""
    agent_name: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass(slots=True)
class ModelUsage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        input_price, output_price = get_pricing(self.model)
        return (
            self.input_tokens / 1_000_000 * input_price
            + self.output_tokens / 1_000_000 * output_price
        )


@dataclass(slots=True)
class RequestUsage:
    by_model: dict[str, ModelUsage] = field(default_factory=dict)
    actual_cost_usd: float | None = None

    def add(
        self,
        *,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        actual_cost_usd: float | None = None,
    ) -> None:
        usage = self.by_model.setdefault(model, ModelUsage(model=model))
        usage.add(input_tokens=input_tokens, output_tokens=output_tokens)

        if actual_cost_usd is not None:
            self.actual_cost_usd = (self.actual_cost_usd or 0.0) + actual_cost_usd

    def add_from_api(
        self,
        *,
        model: str,
        usage: dict,
        actual_cost_usd: float | None = None,
    ) -> None:
        self.add(
            model=model,
            input_tokens=usage.get("input_tokens", 0) or 0,
            output_tokens=usage.get("output_tokens", 0) or 0,
            actual_cost_usd=actual_cost_usd,
        )

    @property
    def total_input_tokens(self) -> int:
        return sum(item.input_tokens for item in self.by_model.values())

    @property
    def total_output_tokens(self) -> int:
        return sum(item.output_tokens for item in self.by_model.values())

    @property
    def estimated_total_cost_usd(self) -> float:
        return sum(item.estimated_cost_usd for item in self.by_model.values())

    @property
    def total_cost_usd(self) -> float:
        return self.actual_cost_usd if self.actual_cost_usd is not None else self.estimated_total_cost_usd

    def is_empty(self) -> bool:
        return not self.by_model

    def to_table(self) -> str:
        if self.is_empty():
            return ""

        lines = [
            f"{'model':<30} {'input':>12} {'output':>12} {'cost':>12}",
            "-" * 72,
        ]

        for item in self.by_model.values():
            lines.append(
                f"{item.model:<30} "
                f"{item.input_tokens:>12,} "
                f"{item.output_tokens:>12,} "
                f"{'~$' + format(item.estimated_cost_usd, '.5f'):>12}"
            )

        lines.append("-" * 72)

        total_cost_prefix = "$" if self.actual_cost_usd is not None else "~$"
        lines.append(
            f"{'total':<30} "
            f"{self.total_input_tokens:>12,} "
            f"{self.total_output_tokens:>12,} "
            f"{(total_cost_prefix + format(self.total_cost_usd, '.5f')):>12}"
        )

        return "\n".join(lines)

    def format(self) -> str:
        """상세 테이블 문자열 반환."""
        return self.to_table()

    def __str__(self) -> str:
        return self.to_table()