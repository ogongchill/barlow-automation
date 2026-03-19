"""refactor 이슈 템플릿 -- RefactorTemplate + to_github_body()."""

from pydantic import BaseModel

from src.domain.common.models.issue_base import BaseIssueTemplate, Label


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


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

    def to_github_body(self) -> str:
        goals_md = ""
        for goal in self.goals:
            goals_md += f"**As-Is**\n{_bullet(goal.as_is)}\n\n**To-Be**\n{_bullet(goal.to_be)}\n\n"
        return (
            f"## 개요\n{self.about}\n\n"
            f"## 변경 목표\n{goals_md}"
            f"## 도메인 규칙\n{_bullet(self.domain_rules)}\n\n"
            f"## 도메인 제약\n{_bullet(self.domain_constraints)}"
        )

    def to_github_payload(self) -> dict:
        return {"title": self.issue_title, "body": self.to_github_body(), "labels": [self.label.value]}
