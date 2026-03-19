"""CreateGithubIssueStep 단위 테스트."""

import httpx
import pytest
import respx

from src.domain.feat.models.issue import FeatTemplate
from src.domain.feat.steps.create_github_issue import (
    CreateGithubIssueInput,
    CreateGithubIssueStep,
)


def _make_input() -> CreateGithubIssueInput:
    template = FeatTemplate(
        issue_title="[FEAT] test",
        about="about",
        goal="goal",
        new_features=["f1"],
        domain_rules=["r1"],
        additional_info="",
    )
    return CreateGithubIssueInput(issue_draft=template.model_dump_json())


@respx.mock
async def test_execute_creates_issue_and_returns_url():
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=httpx.Response(
            201, json={"html_url": "https://github.com/owner/repo/issues/1"}
        )
    )

    step = CreateGithubIssueStep(owner="owner", repo="repo")
    result = await step.execute(_make_input())

    assert result.github_issue_url == "https://github.com/owner/repo/issues/1"


@respx.mock
async def test_execute_raises_on_403():
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=httpx.Response(403)
    )

    step = CreateGithubIssueStep(owner="owner", repo="repo")
    with pytest.raises(httpx.HTTPStatusError):
        await step.execute(_make_input())


async def test_execute_raises_if_invalid_json():
    step = CreateGithubIssueStep(owner="owner", repo="repo")
    with pytest.raises(Exception):
        await step.execute(CreateGithubIssueInput(issue_draft="not-json"))
