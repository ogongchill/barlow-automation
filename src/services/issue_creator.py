"""승인된 이슈 템플릿을 GitHub 이슈로 생성하는 서비스."""

import logging

from src.agent.agent_factory import AgentFactory
from src.domain.pending import PendingRecord

logger = logging.getLogger(__name__)


def _build_create_prompt(record: PendingRecord) -> str:
    return (
        "Create a GitHub issue from the following approved specification.\n\n"
        f"{record.typed_output.model_dump_json(indent=2)}"
    )


async def run_issue_creator(record: PendingRecord) -> str:
    """승인된 이슈 템플릿으로 GitHub 이슈를 생성하고 URL을 반환한다."""
    agent = AgentFactory.issue_writer(record.subcommand)
    prompt = _build_create_prompt(record)
    result = await agent.run(prompt)
    url = (
        result.typed_output.issue_url
        if result.typed_output is not None
        else result.output
    )
    logger.info("issue_creator | created issue url=%s", url)
    return url
