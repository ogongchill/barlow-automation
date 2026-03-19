"""하위 호환 re-export -- 새 경로를 사용하세요."""

from src.domain.common.models.issue_base import Label, BaseIssueTemplate  # noqa: F401
from src.domain.feat.models.issue import FeatTemplate  # noqa: F401
from src.domain.refactor.models.issue import RefactorTemplate  # noqa: F401
from src.domain.fix.models.issue import FixTemplate  # noqa: F401
