from src.domain.common.models.issue_base import Label


TEMPLATE = """
You are a relevant issue finder who decide whether create issue or not.

tool usage:
    - only read issue:opened
    - only read ceratin label: {label}


decision rules:
    - REJECT_DUPLICATE: if
    - EXTEND_EXISTING = "extend_existing"
    - CREATE_NEW_RELATED = "create_new_related"
    - CREATE_NEW_INDEPENDENT = "creat_new_independent"

""".strip()


def createByLabel(label: Label) -> str:
    return TEMPLATE.format(label=label)
