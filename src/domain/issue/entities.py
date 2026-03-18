"""이슈 도메인 모델 — 순수 데이터 구조와 비즈니스 로직만 포함한다."""

from abc import abstractmethod
from enum import Enum

from pydantic import BaseModel


class Label(Enum):
    FEAT = "feat"
    REFACTOR = "refactor"
    FIX = "fix"


class BaseIssueTemplate(BaseModel):
    """모든 이슈 템플릿의 공통 기반."""

    issue_title: str
    about: str

    @property
    @abstractmethod
    def label(self) -> Label: ...


class FeatTemplate(BaseIssueTemplate):
    goal: str
    new_features: list[str]
    domain_rules: list[str]
    additional_info: str

    @property
    def label(self) -> Label:
        return Label.FEAT


class RefactorTemplate(BaseIssueTemplate):

    class _Goal(BaseModel):
        as_is: list[str]
        to_be: list[str]

    domain_rules: list[str]
    domain_constraints: list[str]
    goals: list[_Goal]

    @property
    def label(self) -> Label:
        return Label.REFACTOR


class FixTemplate(BaseIssueTemplate):

    class _Problem(BaseModel):
        issue: str
        suggestion: str

    class _ImplementationStep(BaseModel):
        step: int
        todo: str

    domain_rules: list[str]
    domain_constraints: list[str]
    implementation: list[_ImplementationStep]
    problems: list[_Problem]

    @property
    def label(self) -> Label:
        return Label.FIX
