"""CreateGithubIssueStep 단위 테스트."""
import httpx
import pytest
import respx

from src.domain.feat.models.issue import FeatTemplate
from src.domain.feat.models.state import FeatIssueWorkflowState
from src.domain.feat.steps.create_github_issue import CreateGithubIssueStep


def _make_state(issue_draft: str | None = None) -> FeatIssueWorkflowState:
    template = FeatTemplate(
        issue_title="[FEAT] test",
        about="about",
        goal="goal",
        new_features=["f1"],
        domain_rules=["r1"],
        additional_info="",
    )
    return FeatIssueWorkflowState(
        user_message="msg",
        issue_draft=issue_draft or template.model_dump_json(),
    )


@respx.mock
async def test_execute_creates_issue_and_returns_url():
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=httpx.Response(
            201, json={"html_url": "https://github.com/owner/repo/issues/1"}
        )
    )

    step = CreateGithubIssueStep("feat", owner="owner", repo="repo")
    result = await step.execute(_make_state())

    assert result.status == "success"
    assert result.control_signal == "stop"
    assert result.state_patch["github_issue_url"] == "https://github.com/owner/repo/issues/1"


@respx.mock
async def test_execute_raises_on_403():
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=httpx.Response(403)
    )

    step = CreateGithubIssueStep("feat", owner="owner", repo="repo")
    with pytest.raises(httpx.HTTPStatusError):
        await step.execute(_make_state())


async def test_execute_raises_if_no_issue_draft():
    step = CreateGithubIssueStep("feat", owner="owner", repo="repo")
    state = FeatIssueWorkflowState(user_message="msg", issue_draft=None)
    with pytest.raises(ValueError, match="issue_draft"):
        await step.execute(state)
