"""create_github_issue -- GitHub REST API issue creation + relationship 설정."""

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

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {config.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _create_issue(
        self, client: httpx.AsyncClient, payload: dict
    ) -> tuple[str, int, int]:
        """이슈를 생성하고 (html_url, issue_number, issue_id)를 반환한다."""
        url = f"{GITHUB_API_URL}/repos/{self._owner}/{self._repo}/issues"
        logger.info("github_api | POST %s\n%s", url, payload)
        response = await client.post(url, json=payload, headers=self._headers())
        logger.info("github_api | response status=%s", response.status_code)
        response.raise_for_status()
        data = response.json()
        return data["html_url"], data["number"], data["id"]

    async def _set_parent(
        self, client: httpx.AsyncClient, parent_no: int, child_id: int
    ) -> None:
        """child_id 이슈를 parent_no 이슈의 sub-issue(child)로 설정한다."""
        url = f"{GITHUB_API_URL}/repos/{self._owner}/{self._repo}/issues/{parent_no}/sub_issues"
        payload = {"sub_issue_id": child_id}
        logger.info("github_api | POST %s\n%s", url, payload)
        response = await client.post(url, json=payload, headers=self._headers())
        logger.info("github_api | set_parent response status=%s", response.status_code)
        response.raise_for_status()

    async def _set_blocking(
        self, client: httpx.AsyncClient, anchor_no: int, blocker_id: int
    ) -> None:
        """anchor_no 이슈를 blocker_id 이슈에 의해 blocked 상태로 설정한다.

        anchor가 blocked_by 신규 이슈(blocker).
        POST /issues/{anchor_no}/dependencies/blocked_by + {"issue_id": blocker_id}
        """
        url = f"{GITHUB_API_URL}/repos/{self._owner}/{self._repo}/issues/{anchor_no}/dependencies/blocked_by"
        payload = {"issue_id": blocker_id}
        logger.info("github_api | POST %s\n%s", url, payload)
        response = await client.post(url, json=payload, headers=self._headers())
        logger.info("github_api | set_blocking response status=%s", response.status_code)
        response.raise_for_status()

    async def execute(
        self, input: CreateGithubIssueInput
    ) -> CreateGithubIssueOutput:
        template = FeatTemplate.model_validate_json(input.issue_draft)
        payload = template.to_github_payload()

        anchor_no: int | None = None
        if input.relevant_issues and input.relevant_issues.anchor:
            anchor_no = input.relevant_issues.anchor.issue_no

        async with httpx.AsyncClient() as client:
            html_url, _, issue_id = await self._create_issue(client, payload)

            if input.issue_decision == Decision.EXTEND_EXISTING and anchor_no:
                # 신규 이슈를 anchor의 sub-issue(child)로 설정
                await self._set_parent(client, anchor_no, issue_id)

            elif input.issue_decision == Decision.BLOCK_EXISTING and anchor_no:
                # anchor가 신규 이슈(blocker)에 의해 blocked됨
                await self._set_blocking(client, anchor_no, issue_id)

        logger.info("github_api | issue created url=%s", html_url)
        return CreateGithubIssueOutput(github_issue_url=html_url)
