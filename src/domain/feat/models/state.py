"""Workflow step 간 공유 typed state."""

from dataclasses import dataclass, field

from src.domain.common.models.workflow_instance import register_state_cls


@dataclass
class FeatIssueWorkflowState:
    user_message: str
    bc_candidates: str | None = None      # JSON string
    bc_decision: str | None = None        # JSON string
    issue_draft: str | None = None        # JSON string
    github_issue_url: str | None = None
    user_feedback: str | None = None
    dropped_item_ids: list[str] = field(default_factory=list)

    def apply_patch(self, patch: dict) -> None:
        """state_patch dict를 현재 상태에 반영한다."""
        for key, value in patch.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FeatIssueWorkflowState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# 모든 workflow type에 대해 FeatIssueWorkflowState를 등록한다.
# refactor/fix는 추후 자체 state class로 분리할 수 있다.
register_state_cls("feat_issue", FeatIssueWorkflowState)
register_state_cls("refactor_issue", FeatIssueWorkflowState)
register_state_cls("fix_issue", FeatIssueWorkflowState)
