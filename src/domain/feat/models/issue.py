"""feat 이슈 템플릿 -- FeatTemplate + to_github_body()."""

from src.domain.common.models.issue_base import BaseIssueTemplate, IssueType, Label

# IssueType은 common에서 관리 — 이 모듈에서 re-export하여 하위 호환 유지
__all__ = ["FeatTemplate", "IssueType"]


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


class FeatTemplate(BaseIssueTemplate):
    goal: str
    new_features: list[str]
    domain_rules: list[str]
    additional_info: str

    @property
    def label(self) -> Label:
        return Label.FEAT

    @property
    def issue_type(self) -> IssueType:
        return IssueType.FEAT

    def to_github_body(self) -> str:
        parts = [
            f"## 개요\n{self.about}",
            f"## 목표\n{self.goal}" if self.goal else None,
            f"## 새로운 기능\n{_bullet(self.new_features)}",
            f"## 도메인 규칙\n{_bullet(self.domain_rules)}",
            f"## 추가사항\n{self.additional_info}" if self.additional_info else None,
        ]
        return "\n\n".join(p for p in parts if p is not None)

    def to_github_payload(self) -> dict:
        return {
            "title": self.issue_title,
            "body": self.to_github_body(),
            "labels": [self.label.value],
            "type": self.issue_type.value,
        }
