"""RELEVANT_BC_FINDER agent output schema."""

from pydantic import BaseModel, Field


class RequestGoal(BaseModel):
    summary: str
    usecases: list[str]
    features: list[str]
    domain_rules: list[str]


class Candidate(BaseModel):
    bounded_context: str = Field(..., description="Candidate domain/component/feature name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reason: str


class Candidates(BaseModel):
    items: list[Candidate]
    goal: RequestGoal
