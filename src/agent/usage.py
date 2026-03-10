from dataclasses import dataclass


@dataclass(slots=True)
class AgentUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def format(self) -> str:
        return (
            f"in={self.input_tokens:,} "
            f"out={self.output_tokens:,} "
        )
