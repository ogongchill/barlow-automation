"""inspector 출력을 받아 이슈 템플릿을 생성하는 서비스."""

import logging

from src.agent.agent_factory import AgentFactory
from src.agent.usage import AgentUsage
from src.domain.issue_templates import BaseIssueTemplate

logger = logging.getLogger(__name__)


async def run_issue_generator(
    subcommand: str,
    inspector_output: str,
) -> tuple[BaseIssueTemplate, AgentUsage]:
    """inspector 출력을 받아 이슈 템플릿과 usage를 반환한다.

    Args:
        subcommand: "feat" | "refactor" | "fix"
        inspector_output: read_planner 서비스의 inspector_output 반환값
    Returns:
        (typed_template, usage)
    """
    result = await AgentFactory.issue_gen(subcommand).run(inspector_output)
    logger.debug("issue_gen(%s) done | %s", subcommand, result.usage.format())
    return result.typed_output, result.usage
