"""create_github_issue -- GitHub REST API issue creation."""

import logging

import httpx

from src.config import config
from src.domain.feat.models.issue import FeatTemplate
from src.domain.common.models.step_result import StepResult
from src.domain.feat.models.state import FeatIssueWorkflowState

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


class CreateGithubIssueStep:

    def __init__(self, subcommand: str, owner: str | None = None, repo: str | None = None) -> None:
        self._subcommand = subcommand
        self._owner = owner or config.github_owner
        self._repo = repo or config.github_repo

    async def execute(self, state: FeatIssueWorkflowState) -> StepResult:
        if not state.issue_draft:
            raise ValueError("issue_draft is required")

        template = FeatTemplate.model_validate_json(state.issue_draft)
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
        return StepResult(
            status="success",
            control_signal="stop",
            state_patch={"github_issue_url": issue_url},
        )
