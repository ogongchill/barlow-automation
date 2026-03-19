"""이슈 관련성 판단 도메인 모델."""

from enum import Enum


class Decision(str, Enum):
    REJECT_DUPLICATE = "reject_duplicate"
    EXTEND_EXISTING = "extend_existing"
    CREATE_NEW_RELATED = "create_new_related"
    CREATE_NEW_INDEPENDENT = "create_new_independent"


class RelevantIssueState(str, Enum):
    DUPLICATED = "duplicated"
    EXISTS_RELATED = "exists_related"
    NEW = "new"
