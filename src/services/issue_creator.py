"""승인된 이슈 템플릿을 GitHub REST API로 이슈를 생성하는 서비스."""

import logging

import httpx

from src.config import config
from src.domain.issue_templates import (
    BaseIssueTemplate,
    FeatTemplate,
    FixTemplate,
    RefactorTemplate,
)
from src.domain.pending import PendingRecord

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _format_body(template: BaseIssueTemplate) -> str:
    if isinstance(template, FeatTemplate):
        return (
            f"## 개요\n{template.about}\n\n"
            f"## 새로운 기능\n{_bullet(template.new_features)}\n\n"
            f"## 도메인 규칙\n{_bullet(template.domain_rules)}\n\n"
            f"## 도메인 제약\n{_bullet(template.domain_constraints)}"
        )
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
            f"- **{p.issue}** → {p.suggestion}" for p in template.problems
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


async def run_issue_creator(record: PendingRecord) -> str:
    """승인된 이슈 템플릿으로 GitHub 이슈를 생성하고 URL을 반환한다."""
    template = record.typed_output
    payload = {
        "title": template.issue_title,
        "body": _format_body(template),
        "labels": [template.label.value],
    }
    api_url = (
        f"{_GITHUB_API_BASE}/repos"
        f"/{config.github_owner}/{config.github_repo}/issues"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            api_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {config.github_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    issue_url: str = data["html_url"]
    logger.info("issue_creator | created issue url=%s", issue_url)
    return issue_url
