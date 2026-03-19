"""이슈 관련성 판단 도메인 모델.

Decision 의미:
- REJECT_DUPLICATE: 중복으로 판단, 이슈 생성 안 함
- EXTEND_EXISTING: anchor를 신규 이슈의 parent로 연관
- BLOCK_EXISTING: 신규 이슈가 anchor를 blocking. anchor는 신규 이슈에 의해 blocked됨
- CREATE_NEW_INDEPENDENT: 관련 없는 독립 이슈로 생성
"""

from enum import Enum


class Decision(str, Enum):
    REJECT_DUPLICATE = "reject_duplicate"
    EXTEND_EXISTING = "extend_existing"
    BLOCK_EXISTING = "block_existing"
    CREATE_NEW_INDEPENDENT = "create_new_independent"


class RelevantIssueState(str, Enum):
    DUPLICATED = "duplicated"
    EXISTS_RELATED = "exists_related"
    NEW = "new"
