"""Workflow step 간 공유 typed state."""

from dataclasses import dataclass, field

from src.domain.common.models.workflow_instance import register_state_cls
from src.domain.feat.models.issue_decision import Decision


@dataclass
class FeatIssueWorkflowState:
    user_message: str
    bc_candidates: str | None = None        # out: find_relevant_bc
    bc_decision: str | None = None          # out: (reserved)
    relevant_issues: str | None = None      # out: find_relevant_issue (JSON)
    issue_decision: Decision | None = None  # out: user decision via resume action
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
        return {
            "user_message": self.user_message,
            "bc_candidates": self.bc_candidates,
            "bc_decision": self.bc_decision,
            "relevant_issues": self.relevant_issues,
            "issue_decision": self.issue_decision.value if self.issue_decision else None,
            "issue_draft": self.issue_draft,
            "github_issue_url": self.github_issue_url,
            "completion_message": self.completion_message,
            "user_feedback": self.user_feedback,
            "dropped_item_ids": self.dropped_item_ids,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FeatIssueWorkflowState":
        data = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        if data.get("issue_decision") is not None:
            data["issue_decision"] = Decision(data["issue_decision"])
        return cls(**data)


register_state_cls("feat_issue", FeatIssueWorkflowState)
register_state_cls("refactor_issue", FeatIssueWorkflowState)
register_state_cls("fix_issue", FeatIssueWorkflowState)
