"""fix 이슈 템플릿 -- FixTemplate + to_github_body()."""

from pydantic import BaseModel

from src.domain.common.models.issue_base import BaseIssueTemplate, IssueType, Label


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


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

    @property
    def issue_type(self) -> IssueType:
        return IssueType.FIX

    def to_github_body(self) -> str:
        problems_md = "\n".join(
            f"- **{p.issue}** -> {p.suggestion}" for p in self.problems
        )
        impl_md = "\n".join(f"{s.step}. {s.todo}" for s in self.implementation)
        return (
            f"## 개요\n{self.about}\n\n"
            f"## 문제 및 제안\n{problems_md}\n\n"
            f"## 구현 단계\n{impl_md}\n\n"
            f"## 도메인 규칙\n{_bullet(self.domain_rules)}\n\n"
            f"## 도메인 제약\n{_bullet(self.domain_constraints)}"
        )

    def to_github_payload(self) -> dict:
        return {
            "title": self.issue_title,
            "body": self.to_github_body(),
            "labels": [self.label.value],
            "type": self.issue_type.value,
        }
