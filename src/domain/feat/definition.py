"""feat_issue 워크플로우 step 그래프 정의."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StepNode:
    step_name: str
    on_continue: str | None = None
    on_wait: str | None = None
    on_stop: str | None = None


GRAPH: dict[str, StepNode] = {
    "find_relevant_bc":       StepNode("find_relevant_bc",       on_continue="generate_issue_draft"),
    "generate_issue_draft":   StepNode("generate_issue_draft",   on_continue="wait_confirmation"),
    "wait_confirmation":      StepNode("wait_confirmation",      on_wait=None),
    "regenerate_issue_draft": StepNode("regenerate_issue_draft", on_continue="wait_confirmation"),
    "create_github_issue":    StepNode("create_github_issue",    on_stop=None),
}
WORKFLOW_TYPE = "feat_issue"
FIRST_STEP = "find_relevant_bc"
RESUME_MAP: dict[str, str] = {
    "accept":       "create_github_issue",
    "reject":       "regenerate_issue_draft",
    "drop_restart": "regenerate_issue_draft",
}
