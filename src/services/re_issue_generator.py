"""기존 PendingRecord 컨텍스트를 기반으로 이슈를 재생성하는 서비스."""

import logging

from src.agent.agent_factory import AgentFactory
from src.agent.usage import AgentUsage
from src.domain.issue_templates import BaseIssueTemplate
from src.domain.pending import PendingRecord

logger = logging.getLogger(__name__)


def _build_prompt(record: PendingRecord, additional_requirements: str | None) -> str:
    """reissue_gen 에이전트에 전달할 프롬프트를 구성한다."""
    parts = [
        f"[Inspector Context]\n{record.inspector_output}",
        f"[Current Issue Draft]\n{record.typed_output.model_dump_json(indent=2)}",
    ]
    if additional_requirements:
        parts.append(f"Additional requirements: {additional_requirements}")
    return "\n\n".join(parts)


async def run_re_issue_generator(
    record: PendingRecord,
    additional_requirements: str | None = None,
) -> tuple[BaseIssueTemplate, AgentUsage]:
    """기존 PendingRecord를 바탕으로 이슈를 재생성하고 템플릿과 usage를 반환한다.

    Args:
        record: 재요청 대상 PendingRecord
        additional_requirements: 사용자가 입력한 추가 요구사항 (없으면 None)
    Returns:
        (typed_template, usage)
    """
    prompt = _build_prompt(record, additional_requirements)
    result = await AgentFactory.reissue_gen(record.subcommand).run(prompt)
    logger.debug("reissue_gen(%s) done | %s", record.subcommand, result.usage.format())
    return result.typed_output, result.usage
