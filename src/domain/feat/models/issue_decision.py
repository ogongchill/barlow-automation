from enum import Enum


class Decision(str, Enum):

    REJECT_DUPLICATE = "reject_duplicate"
    EXTEND_EXISTING = "extend_existing"
    CREATE_NEW_RELATED = "create_new_related"
    CREATE_NEW_INDEPENDENT = "creat_new_independent"
