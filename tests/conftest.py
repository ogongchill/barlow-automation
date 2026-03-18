"""Root conftest -- patches boto3 and sets env vars BEFORE any src imports."""

import os

os.environ.update({
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "SLACK_SIGNING_SECRET": "test-signing-secret",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "GITHUB_TOKEN": "ghp_test_token",
    "OPENAI_API_KEY": "sk-test-openai",
    "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789/test-queue",
    "TARGET_REPO": "test-owner/test-repo",
})

import unittest.mock  # noqa: E402
import boto3  # noqa: E402

boto3.client = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock())
boto3.resource = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock())

import pytest  # noqa: E402

import time  # noqa: E402

from src.domain.issue_templates import (  # noqa: E402
    FeatTemplate,
    RefactorTemplate,
    FixTemplate,
)
from src.agent.base import AgentResult  # noqa: E402
from src.agent.usage import AgentUsage  # noqa: E402
from src.workflow.models.workflow_state import FeatIssueWorkflowState  # noqa: E402
from src.workflow.models.workflow_instance import WorkflowInstance  # noqa: E402
from src.workflow.models.lifecycle import WorkflowStatus  # noqa: E402
from src.workflow.models.step_result import StepResult  # noqa: E402


@pytest.fixture()
def feat_template() -> FeatTemplate:
    return FeatTemplate(
        issue_title="[FEAT] Add bookmark feature",
        about="Users need a way to bookmark items for quick access.",
        goal="북마크 기능을 통해 사용자가 자주 접근하는 항목을 빠르게 찾을 수 있도록 한다.",
        new_features=[
            "User can bookmark any item",
            "User can view bookmarked items list",
            "User can remove a bookmark",
        ],
        domain_rules=["Only authenticated users can bookmark"],
        additional_info="",
    )


@pytest.fixture()
def refactor_template() -> RefactorTemplate:
    return RefactorTemplate(
        issue_title="[REFACTOR] Extract session interface",
        about="SessionManager has too many responsibilities.",
        goals=[
            RefactorTemplate._Goal(
                as_is=["SessionManager directly creates InMemoryStore"],
                to_be=["SessionManager depends on IStore interface"],
            ),
            RefactorTemplate._Goal(
                as_is=["Logging mixed into business logic"],
                to_be=["Logging extracted to decorator"],
            ),
        ],
        domain_rules=["Preserve backward compatibility"],
        domain_constraints=["No new external dependencies"],
    )


@pytest.fixture()
def fix_template() -> FixTemplate:
    return FixTemplate(
        issue_title="[FIX] Resolve NPE on login",
        about="NullPointerException occurs when user profile is missing.",
        problems=[
            FixTemplate._Problem(
                issue="User profile can be null after OAuth",
                suggestion="Add null check before accessing profile fields",
            ),
        ],
        implementation=[
            FixTemplate._ImplementationStep(step=1, todo="Add null guard in AuthService.login()"),
        ],
        domain_rules=["Must not break existing login flow"],
        domain_constraints=["Keep changes within auth module"],
    )


@pytest.fixture()
def make_agent_result():
    """Factory fixture that returns a callable producing AgentResult instances."""

    def _factory(
        output: str = "test output",
        typed_output=None,
        in_tokens: int = 10,
        out_tokens: int = 5,
    ) -> AgentResult:
        return AgentResult(
            output=output,
            usage=AgentUsage(input_tokens=in_tokens, output_tokens=out_tokens),
            typed_output=typed_output,
        )

    return _factory


@pytest.fixture()
def feat_workflow_state() -> FeatIssueWorkflowState:
    return FeatIssueWorkflowState(user_message="[feat] 즐겨찾기 기능 추가")


@pytest.fixture()
def feat_workflow_instance(feat_workflow_state: FeatIssueWorkflowState) -> WorkflowInstance:
    return WorkflowInstance(
        workflow_id="wf-123",
        workflow_type="feat_issue",
        status=WorkflowStatus.RUNNING,
        current_step="find_relevant_bc",
        state=feat_workflow_state,
        pending_action_token=None,
        slack_channel_id="C1",
        slack_user_id="U1",
        slack_message_ts=None,
        created_at=int(time.time()),
        ttl=int(time.time()) + 86400,
    )


@pytest.fixture()
def success_step_result() -> StepResult:
    return StepResult(status="success", control_signal="continue")
