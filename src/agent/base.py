"""
Agent 추상 계층.

IAgent: 모든 에이전트가 구현해야 하는 인터페이스.
고수준 모듈(handlers, app, main)은 IAgent에만 의존한다.
구체 구현(ClaudeAgent, OpenAIAgent)은 runner/ 에 위치하며,
agents/ 에서 생성되어 IAgent로 주입된다 (DIP).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from src.agent.usage import AgentUsage
from typing import Any


@dataclass
class AgentResult:
    output: str
    usage: AgentUsage
    raw: Any = field(default=None)          # SDK별 raw 응답 (RunResult, ClaudeResult 등)
    typed_output: Any = field(default=None)  # output_type 지정 시 파싱된 Pydantic 인스턴스


class IAgent(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @abstractmethod
    async def run(self, message: str) -> AgentResult: ...
