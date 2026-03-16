"""READ_PLANNER → READ_TARGET_INSPECTOR 2단계 파이프라인 서비스."""

import logging

from src.agent.agent_factory import AgentFactory
from src.agent.usage import AgentUsage

logger = logging.getLogger(__name__)


async def run_read_planner(user_message: str) -> tuple[str, AgentUsage]:
    """user_message를 받아 inspector 출력 문자열과 누적 usage를 반환한다.

    Returns:
        (inspector_output, usage)
        - inspector_output: READ_TARGET_INSPECTOR의 typed_output JSON 문자열
        - usage: 두 에이전트의 토큰 사용량 합산
    """
    usage = AgentUsage()

    planner_result = await AgentFactory.read_planner().run(user_message)
    usage.add(
        input_tokens=planner_result.usage.input_tokens,
        output_tokens=planner_result.usage.output_tokens,
    )
    logger.debug("read_planner done | %s", planner_result.usage.format())

    inspector_result = await AgentFactory.inspector().run(planner_result.output)
    usage.add(
        input_tokens=inspector_result.usage.input_tokens,
        output_tokens=inspector_result.usage.output_tokens,
    )
    logger.debug("inspector done | %s", inspector_result.usage.format())

    return inspector_result.output, usage
