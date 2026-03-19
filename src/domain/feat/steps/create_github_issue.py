"""create_github_issue -- GitHub REST API issue creation."""

import logging
from dataclasses import dataclass

import httpx

from src.config import config
from src.domain.feat.agents.relevant_issue_finder.schema import RelevantIssue
from src.domain.feat.models.issue import FeatTemplate
from src.domain.feat.models.issue_decision import Decision

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


@dataclass(frozen=True)
class CreateGithubIssueInput:
    issue_draft: str
    issue_decision: Decision | None = None
    relevant_issues: RelevantIssue | None = None


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

        anchor = input.relevant_issues.anchor
        anchor_no = anchor.issue_no if anchor else None

        body: str = payload.get("body", "")

        if input.issue_decision == Decision.EXTEND_EXISTING and anchor_no:
            body = f"Extends #{anchor_no}\n\n{body}"
            payload["labels"] = payload.get("labels", []) + ["extends"]
        elif input.issue_decision == Decision.CREATE_NEW_RELATED and anchor_no:
            body = f"Related to #{anchor_no}\n\n{body}"

        payload["body"] = body
        return payload

    async def execute(
        self, input: CreateGithubIssueInput
    ) -> CreateGithubIssueOutput:
        template = FeatTemplate.model_validate_json(input.issue_draft)
        payload = self._enrich_payload(template.to_github_payload(), input)

        url = f"{GITHUB_API_URL}/repos/{self._owner}/{self._repo}/issues"
        logger.info("github_api | POST %s\n%s", url, payload)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {config.github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            logger.info(
                "github_api | response status=%s", response.status_code
            )
            response.raise_for_status()
            issue_url = response.json()["html_url"]

        logger.info("github_api | issue created url=%s", issue_url)
        return CreateGithubIssueOutput(github_issue_url=issue_url)
