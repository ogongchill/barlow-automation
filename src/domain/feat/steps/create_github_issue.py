"""create_github_issue -- GitHub REST API issue creation."""

import json
import logging
from dataclasses import dataclass

import httpx

from src.config import config
from src.domain.feat.models.issue import FeatTemplate

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


@dataclass(frozen=True)
class CreateGithubIssueInput:
    issue_draft: str
    issue_decision: str | None = None
    relevant_issues: str | None = None


@dataclass(frozen=True)
class CreateGithubIssueOutput:
    github_issue_url: str


class CreateGithubIssueStep:

    def __init__(
        self,
        owner: str | None = None,
        repo: str | None = None,
    ) -> None:
        self._owner = owner or config.github_owner
        self._repo = repo or config.github_repo

    def _enrich_payload(self, payload: dict, input: CreateGithubIssueInput) -> dict:
        """issue_decision에 따라 payload body를 보강한다."""
        if not input.issue_decision or not input.relevant_issues:
            return payload

        try:
            ri = json.loads(input.relevant_issues)
            anchor = ri.get("anchor") or {}
            anchor_no = anchor.get("issue_no")
        except (json.JSONDecodeError, AttributeError):
            return payload

        body: str = payload.get("body", "")

        if input.issue_decision == "extend_existing" and anchor_no:
            body = f"Extends #{anchor_no}\n\n{body}"
            payload["labels"] = payload.get("labels", []) + ["extends"]
        elif input.issue_decision == "create_new_related" and anchor_no:
            body = f"Related to #{anchor_no}\n\n{body}"

        payload["body"] = body
        return payload

    async def execute(
        self, input: CreateGithubIssueInput
    ) -> CreateGithubIssueOutput:
        template = FeatTemplate.model_validate_json(input.issue_draft)
        payload = self._enrich_payload(template.to_github_payload(), input)

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
        return CreateGithubIssueOutput(github_issue_url=issue_url)
