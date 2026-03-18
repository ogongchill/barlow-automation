"""create_github_issue_step -- GitHub REST API issue creation."""

import json
import logging

import httpx

from src.config import config
from src.domain.issue.entities import (
    BaseIssueTemplate,
    FeatTemplate,
    FixTemplate,
    RefactorTemplate,
)
from src.workflow.models.step_result import StepResult
from src.workflow.models.workflow_state import FeatIssueWorkflowState

logger = logging.getLogger(__name__)

_TEMPLATE_CLS: dict[str, type[BaseIssueTemplate]] = {
    "feat": FeatTemplate,
    "refactor": RefactorTemplate,
    "fix": FixTemplate,
}

GITHUB_API_URL = "https://api.github.com"


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _format_body(template: BaseIssueTemplate) -> str:
    """template to GitHub issue body markdown."""
    if isinstance(template, FeatTemplate):
        parts = [
            f"## 개요\n{template.about}",
            f"## 목표\n{template.goal}" if template.goal else None,
            f"## 새로운 기능\n{_bullet(template.new_features)}",
            f"## 도메인 규칙\n{_bullet(template.domain_rules)}",
            f"## 추가사항\n{template.additional_info}" if template.additional_info else None,
        ]
        return "\n\n".join(p for p in parts if p is not None)
    if isinstance(template, RefactorTemplate):
        goals_md = ""
        for goal in template.goals:
            goals_md += f"**As-Is**\n{_bullet(goal.as_is)}\n\n**To-Be**\n{_bullet(goal.to_be)}\n\n"
        return (
            f"## 개요\n{template.about}\n\n"
            f"## 변경 목표\n{goals_md}"
            f"## 도메인 규칙\n{_bullet(template.domain_rules)}\n\n"
            f"## 도메인 제약\n{_bullet(template.domain_constraints)}"
        )
    if isinstance(template, FixTemplate):
        problems_md = "\n".join(
            f"- **{p.issue}** -> {p.suggestion}" for p in template.problems
        )
        impl_md = "\n".join(f"{s.step}. {s.todo}" for s in template.implementation)
        return (
            f"## 개요\n{template.about}\n\n"
            f"## 문제 및 제안\n{problems_md}\n\n"
            f"## 구현 단계\n{impl_md}\n\n"
            f"## 도메인 규칙\n{_bullet(template.domain_rules)}\n\n"
            f"## 도메인 제약\n{_bullet(template.domain_constraints)}"
        )
    return template.model_dump_json(indent=2)


def _build_payload(template: BaseIssueTemplate) -> dict:
    return {
        "title": template.issue_title,
        "body": _format_body(template),
        "labels": [template.label.value],
    }


class CreateGithubIssueStep:

    def __init__(self, subcommand: str, owner: str | None = None, repo: str | None = None) -> None:
        self._subcommand = subcommand
        self._owner = owner or config.github_owner
        self._repo = repo or config.github_repo

    async def execute(self, state: FeatIssueWorkflowState) -> StepResult:
        if not state.issue_draft:
            raise ValueError("issue_draft is required")

        template_cls = _TEMPLATE_CLS.get(self._subcommand, FeatTemplate)
        template = template_cls.model_validate_json(state.issue_draft)
        payload = _build_payload(template)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/repos/{self._owner}/{self._repo}/issues",
                json=payload,
                headers={
                    "Authorization": f"Bearer {config.github_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            issue_url = response.json()["html_url"]

        logger.info("GitHub issue created: %s", issue_url)
        return StepResult(
            status="success",
            control_signal="stop",
            state_patch={"github_issue_url": issue_url},
        )
