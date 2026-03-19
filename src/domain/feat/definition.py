"""feat_issue 워크플로우 step 그래프 정의."""

from dataclasses import dataclass
from typing import Any, Callable

from src.domain.common.models.step_result import ControlSignal
from src.domain.feat.steps.create_github_issue import (
    CreateGithubIssueInput,
    CreateGithubIssueStep,
)
from src.domain.feat.steps.find_relevant_bc import (
    FindRelevantBcInput,
    FindRelevantBcStep,
)
from src.domain.feat.steps.generate_issue_draft import (
    GenerateIssueDraftInput,
    GenerateIssueDraftStep,
)
from src.domain.feat.steps.regenerate_issue_draft import (
    RegenerateIssueDraftInput,
    RegenerateIssueDraftStep,
)
from src.domain.feat.steps.wait_confirmation import (
    WaitConfirmationInput,
    WaitConfirmationStep,
)


@dataclass(frozen=True)
class StepNode:
    step: Any
    control_signal: ControlSignal
    extract_input: Callable[..., Any]
    apply_output: Callable[..., None]
    on_continue: str | None = None
    on_wait: str | None = None
    on_stop: str | None = None
    extract_user_action: Callable[[Any], dict] | None = None


GRAPH: dict[str, StepNode] = {
    "find_relevant_bc": StepNode(
        step=FindRelevantBcStep(),
        control_signal=ControlSignal.CONTINUE,
        extract_input=lambda inst: FindRelevantBcInput(
            user_message=inst.state.user_message,
        ),
        apply_output=lambda s, o: setattr(s, "bc_candidates", o.bc_candidates),
        on_continue="generate_issue_draft",
    ),
    "generate_issue_draft": StepNode(
        step=GenerateIssueDraftStep(),
        control_signal=ControlSignal.CONTINUE,
        extract_input=lambda inst: GenerateIssueDraftInput(
            bc_candidates=inst.state.bc_candidates,
            bc_decision=inst.state.bc_decision,
        ),
        apply_output=lambda s, o: setattr(s, "issue_draft", o.issue_draft),
        on_continue="wait_confirmation",
    ),
    "wait_confirmation": StepNode(
        step=WaitConfirmationStep(),
        control_signal=ControlSignal.WAIT_FOR_USER,
        extract_input=lambda inst: WaitConfirmationInput(
            issue_draft=inst.state.issue_draft,
            workflow_id=inst.workflow_id,
            user_id=inst.slack_user_id,
        ),
        apply_output=lambda s, o: None,
        extract_user_action=lambda o: {"blocks": o.blocks},
    ),
    "regenerate_issue_draft": StepNode(
        step=RegenerateIssueDraftStep(),
        control_signal=ControlSignal.CONTINUE,
        extract_input=lambda inst: RegenerateIssueDraftInput(
            bc_candidates=inst.state.bc_candidates,
            issue_draft=inst.state.issue_draft,
            user_feedback=inst.state.user_feedback,
        ),
        apply_output=lambda s, o: setattr(s, "issue_draft", o.issue_draft),
        on_continue="wait_confirmation",
    ),
    "create_github_issue": StepNode(
        step=CreateGithubIssueStep(),
        control_signal=ControlSignal.STOP,
        extract_input=lambda inst: CreateGithubIssueInput(
            issue_draft=inst.state.issue_draft,
        ),
        apply_output=lambda s, o: setattr(
            s, "github_issue_url", o.github_issue_url
        ),
    ),
}
WORKFLOW_TYPE = "feat_issue"
FIRST_STEP = "find_relevant_bc"
RESUME_MAP: dict[str, str] = {
    "accept": "create_github_issue",
    "reject": "regenerate_issue_draft",
    "drop_restart": "regenerate_issue_draft",
}
