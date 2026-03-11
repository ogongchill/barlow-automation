from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel


class Label(Enum):
    FEAT = "feat"
    REFACTOR = "refactor"
    FIX = "fix"


@dataclass
class DroppableItem:
    """Modal 체크박스로 제외 가능한 항목."""
    id: str       # e.g. "new_features::0" — 체크박스 value
    section: str  # 섹션 레이블 (그룹핑용)
    text: str     # 화면에 표시할 텍스트


def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {item}" for item in items)


class BaseIssueTemplate(BaseModel):
    """모든 이슈 템플릿의 공통 기반."""

    issue_title: str
    about: str

    @property
    def title(self) -> str:
        return self.issue_title

    @property
    def about_text(self) -> str:
        return self.about

    @property
    @abstractmethod
    def label(self) -> Label: ...

    @abstractmethod
    def slack_format(self) -> str:
        """Slack mrkdwn 형식으로 이슈 내용을 반환한다."""
        ...

    @abstractmethod
    def droppable_items(self) -> list[DroppableItem]:
        """Modal 체크박스에 표시할 항목 목록을 반환한다."""
        ...


class FeatTemplate(BaseIssueTemplate):
    new_features: list[str]
    domain_rules: list[str]
    domain_constraints: list[str]

    @property
    def label(self) -> Label:
        return Label.FEAT

    def slack_format(self) -> str:
        return "\n\n".join([
            f"*{self.issue_title}*",
            self.about,
            f"*신규 기능*\n{_bullets(self.new_features)}",
            f"*도메인 규칙*\n{_bullets(self.domain_rules)}",
            f"*기술 제약*\n{_bullets(self.domain_constraints)}",
        ])

    def droppable_items(self) -> list[DroppableItem]:
        items: list[DroppableItem] = []
        for i, item in enumerate(self.new_features):
            items.append(DroppableItem(id=f"new_features::{i}", section="신규 기능", text=item))
        for i, item in enumerate(self.domain_rules):
            items.append(DroppableItem(id=f"domain_rules::{i}", section="도메인 규칙", text=item))
        for i, item in enumerate(self.domain_constraints):
            items.append(DroppableItem(id=f"domain_constraints::{i}", section="기술 제약", text=item))
        return items


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

    def slack_format(self) -> str:
        goal_lines = []
        for i, goal in enumerate(self.goals, start=1):
            as_is_text = _bullets(goal.as_is)
            to_be_text = _bullets(goal.to_be)
            goal_lines.append(f"*목표 {i}*\n_AS-IS_\n{as_is_text}\n_TO-BE_\n{to_be_text}")

        return "\n\n".join([
            f"*{self.issue_title}*",
            self.about,
            *goal_lines,
            f"*도메인 규칙*\n{_bullets(self.domain_rules)}",
            f"*기술 제약*\n{_bullets(self.domain_constraints)}",
        ])

    def droppable_items(self) -> list[DroppableItem]:
        items: list[DroppableItem] = []
        for i, goal in enumerate(self.goals):
            as_is = goal.as_is[0] if goal.as_is else ""
            to_be = goal.to_be[0] if goal.to_be else ""
            items.append(DroppableItem(id=f"goals::{i}", section=f"목표 {i + 1}", text=f"{as_is} → {to_be}"))
        for i, item in enumerate(self.domain_rules):
            items.append(DroppableItem(id=f"domain_rules::{i}", section="도메인 규칙", text=item))
        for i, item in enumerate(self.domain_constraints):
            items.append(DroppableItem(id=f"domain_constraints::{i}", section="기술 제약", text=item))
        return items


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

    def slack_format(self) -> str:
        problem_lines = "\n".join(
            f"• *문제:* {p.issue}\n  *제안:* {p.suggestion}"
            for p in self.problems
        )
        impl_lines = "\n".join(
            f"{s.step}. {s.todo}" for s in self.implementation
        )
        return "\n\n".join([
            f"*{self.issue_title}*",
            self.about,
            f"*문제 및 해결 방안*\n{problem_lines}",
            f"*구현 단계*\n{impl_lines}",
            f"*도메인 규칙*\n{_bullets(self.domain_rules)}",
            f"*기술 제약*\n{_bullets(self.domain_constraints)}",
        ])

    def droppable_items(self) -> list[DroppableItem]:
        items: list[DroppableItem] = []
        for i, p in enumerate(self.problems):
            items.append(DroppableItem(id=f"problems::{i}", section="문제", text=p.issue))
        for i, s in enumerate(self.implementation):
            items.append(DroppableItem(id=f"implementation::{i}", section="구현 단계", text=f"{s.step}. {s.todo}"))
        for i, item in enumerate(self.domain_rules):
            items.append(DroppableItem(id=f"domain_rules::{i}", section="도메인 규칙", text=item))
        for i, item in enumerate(self.domain_constraints):
            items.append(DroppableItem(id=f"domain_constraints::{i}", section="기술 제약", text=item))
        return items
