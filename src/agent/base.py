"""
Agent 추상 계층.

IAgent: 모든 에이전트가 구현해야 하는 인터페이스.
고수준 모듈(handlers, app, main)은 IAgent에만 의존한다.
구체 구현(ClaudeAgent, OpenAIAgent)은 runner/ 에 위치하며,
agents/ 에서 생성되어 IAgent로 주입된다 (DIP).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.agent.usage import RequestUsage, TurnUsage


@dataclass
class AgentResult:
    """IAgent.run()의 공통 반환 포맷."""
    output: str
    usage: RequestUsage
    turns: list[TurnUsage] = field(default_factory=list)  # agent/turn별 세부 사용량
    raw: Any = field(default=None)  # SDK별 raw 응답 (RunResult, ClaudeResult 등)


class IAgent(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @abstractmethod
    async def run(self, message: str) -> AgentResult: ...
