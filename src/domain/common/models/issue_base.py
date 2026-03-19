"""이슈 템플릿 공통 기반 -- Label enum 및 BaseIssueTemplate."""

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
