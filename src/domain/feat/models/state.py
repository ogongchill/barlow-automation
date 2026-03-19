"""Workflow step 간 공유 typed state."""

from dataclasses import dataclass, field

from src.domain.common.models.workflow_instance import register_state_cls


@dataclass
class FeatIssueWorkflowState:
    user_message: str
    bc_candidates: str | None = None        # out: find_relevant_bc
    bc_decision: str | None = None          # out: (reserved)
    relevant_issues: str | None = None      # out: find_relevant_issue (JSON)
    issue_decision: str | None = None       # out: user decision via resume action
    issue_draft: str | None = None          # out: generate_issue_draft / regenerate
    github_issue_url: str | None = None     # out: create_github_issue
    completion_message: str | None = None   # out: reject_end
    user_feedback: str | None = None
    dropped_item_ids: list[str] = field(default_factory=list)

    def apply_patch(self, patch: dict) -> None:
        for key, value in patch.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FeatIssueWorkflowState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


register_state_cls("feat_issue", FeatIssueWorkflowState)
register_state_cls("refactor_issue", FeatIssueWorkflowState)
register_state_cls("fix_issue", FeatIssueWorkflowState)
