from dataclasses import Field
from pydantic import BaseModel
from src.domain.feat.models.issue_decision import Decision


class _RelatedIssue(BaseModel):
    issue_no: str
    confidence: float


class IssueRelationDecision(BaseModel):
    decision: Decision
    existing_issue_number: int | None = None
    reason: str
    anchor_issue_number: int | None = None
    anchor_reason: str | None = None
    related_issues: list[_RelatedIssue] = Field(default_factory=list)
