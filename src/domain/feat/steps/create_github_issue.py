"""create_github_issue -- GitHub REST API issue creation."""

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

    async def execute(
        self, input: CreateGithubIssueInput
    ) -> CreateGithubIssueOutput:
        template = FeatTemplate.model_validate_json(input.issue_draft)
        payload = template.to_github_payload()

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
