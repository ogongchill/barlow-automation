from src.domain.feat.models.issue_decision import RelevantIssueState
from pydantic import BaseModel, Field


class _RelatedIssue(BaseModel):
    issue_no: str = Field(..., description="Existing related issue number")
    confidence: float = Field(..., ge=0.0, le=1.0)


class _AnchorIssue(BaseModel):
    issue_no: str = Field(..., description="Best matching existing issue number")
    issue_url: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: list[str] = Field(
        default_factory=list,
        description="Concrete reasons why this issue is the anchor"
    )


class RelevantIssue(BaseModel):
    state: RelevantIssueState
    anchor: _AnchorIssue | None = None
    related_issues: list[_RelatedIssue] = Field(default_factory=list)