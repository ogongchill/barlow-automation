"""RELEVANT_BC_FINDER 에이전트 서비스."""

import logging

from src.agent.agent_factory import AgentFactory
from src.agent.usage import AgentUsage

logger = logging.getLogger(__name__)


async def run_read_planner(user_message: str) -> tuple[str, AgentUsage]:
    """user_message를 받아 bc_finder 출력 문자열과 usage를 반환한다.

    Returns:
        (bc_finder_output, usage)
        - bc_finder_output: RELEVANT_BC_FINDER의 typed_output JSON 문자열
    """
    usage = AgentUsage()

    bc_finder_result = await AgentFactory.relevant_bc_finder().run(user_message)
    usage.add(
        input_tokens=bc_finder_result.usage.input_tokens,
        output_tokens=bc_finder_result.usage.output_tokens,
    )
    logger.debug("bc_finder done | %s", bc_finder_result.usage.format())

    return bc_finder_result.output, usage
