"""Modal 드롭 기능 — DroppableItem 생성 및 dropped_ids 기반 템플릿 필터링."""

from dataclasses import dataclass
from functools import singledispatch

from src.domain.issue_templates import (
    BaseIssueTemplate,
    FeatTemplate,
    RefactorTemplate,
    FixTemplate,
)


@dataclass
class DroppableItem:
    """Modal 체크박스로 제외 가능한 항목."""

    id: str       # e.g. "new_features::0" — 체크박스 value
    section: str  # 섹션 레이블 (그룹핑용)
    text: str     # 화면에 표시할 텍스트


def _item_id(field: str, index: int) -> str:
    return f"{field}::{index}"


def _drop(items: list, field: str, dropped_ids: set[str]) -> list:
    return [v for i, v in enumerate(items) if _item_id(field, i) not in dropped_ids]


def _to_droppable(items: list[str], field: str, section: str) -> list[DroppableItem]:
    return [DroppableItem(id=_item_id(field, i), section=section, text=v) for i, v in enumerate(items)]


# ── droppable_items ───────────────────────────────────────────────────────────

@singledispatch
def droppable_items(template: BaseIssueTemplate) -> list[DroppableItem]:
    """템플릿에서 Modal 체크박스 항목 목록을 반환한다."""
    raise NotImplementedError(f"droppable_items not implemented for {type(template)}")


@droppable_items.register
def _(template: FeatTemplate) -> list[DroppableItem]:
    return [
        *_to_droppable(template.new_features, "new_features", "신규 기능"),
        *_to_droppable(template.domain_rules, "domain_rules", "도메인 규칙"),
    ]


@droppable_items.register
def _(template: RefactorTemplate) -> list[DroppableItem]:
    goal_items = [
        DroppableItem(
            id=_item_id("goals", i),
            section=f"목표 {i + 1}",
            text=f"{goal.as_is[0] if goal.as_is else ''} → {goal.to_be[0] if goal.to_be else ''}",
        )
        for i, goal in enumerate(template.goals)
    ]
    return [
        *goal_items,
        *_to_droppable(template.domain_rules, "domain_rules", "도메인 규칙"),
        *_to_droppable(template.domain_constraints, "domain_constraints", "기술 제약"),
    ]


@droppable_items.register
def _(template: FixTemplate) -> list[DroppableItem]:
    return [
        *[DroppableItem(id=_item_id("problems", i), section="문제", text=p.issue) for i, p in enumerate(template.problems)],
        *[DroppableItem(id=_item_id("implementation", i), section="구현 단계", text=f"{s.step}. {s.todo}") for i, s in enumerate(template.implementation)],
        *_to_droppable(template.domain_rules, "domain_rules", "도메인 규칙"),
        *_to_droppable(template.domain_constraints, "domain_constraints", "기술 제약"),
    ]


# ── drop_items ────────────────────────────────────────────────────────────────

@singledispatch
def drop_items(template: BaseIssueTemplate, dropped_ids: set[str]) -> BaseIssueTemplate:
    """dropped_ids에 해당하는 항목을 제거한 새 템플릿 인스턴스를 반환한다."""
    raise NotImplementedError(f"drop_items not implemented for {type(template)}")


@drop_items.register
def _(template: FeatTemplate, dropped_ids: set[str]) -> FeatTemplate:
    return template.model_copy(update={
        "new_features": _drop(template.new_features, "new_features", dropped_ids),
        "domain_rules": _drop(template.domain_rules, "domain_rules", dropped_ids),
    })


@drop_items.register
def _(template: RefactorTemplate, dropped_ids: set[str]) -> RefactorTemplate:
    return template.model_copy(update={
        "goals": _drop(template.goals, "goals", dropped_ids),
        "domain_rules": _drop(template.domain_rules, "domain_rules", dropped_ids),
        "domain_constraints": _drop(template.domain_constraints, "domain_constraints", dropped_ids),
    })


@drop_items.register
def _(template: FixTemplate, dropped_ids: set[str]) -> FixTemplate:
    return template.model_copy(update={
        "problems": _drop(template.problems, "problems", dropped_ids),
        "implementation": _drop(template.implementation, "implementation", dropped_ids),
        "domain_rules": _drop(template.domain_rules, "domain_rules", dropped_ids),
        "domain_constraints": _drop(template.domain_constraints, "domain_constraints", dropped_ids),
    })
