"""하위 호환 re-export — src.domain.issue.entities를 사용하세요."""

from src.domain.issue.entities import *  # noqa: F401, F403
from src.domain.issue.entities import Label, BaseIssueTemplate, FeatTemplate, RefactorTemplate, FixTemplate
