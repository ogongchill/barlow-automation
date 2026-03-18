"""GitHub Issue 페이로드 빌더 -- create_github_issue_step에서 분리."""

from src.domain.issue.entities import (
    BaseIssueTemplate,
    FeatTemplate,
    FixTemplate,
    RefactorTemplate,
)


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _format_body(template: BaseIssueTemplate) -> str:
    """template을 GitHub issue body markdown으로 변환한다."""
    if isinstance(template, FeatTemplate):
        parts = [
            f"## 개요\n{template.about}",
            f"## 목표\n{template.goal}" if template.goal else None,
            f"## 새로운 기능\n{_bullet(template.new_features)}",
            f"## 도메인 규칙\n{_bullet(template.domain_rules)}",
            f"## 추가사항\n{template.additional_info}" if template.additional_info else None,
        ]
        return "\n\n".join(p for p in parts if p is not None)
    if isinstance(template, RefactorTemplate):
        goals_md = ""
        for goal in template.goals:
            goals_md += f"**As-Is**\n{_bullet(goal.as_is)}\n\n**To-Be**\n{_bullet(goal.to_be)}\n\n"
        return (
            f"## 개요\n{template.about}\n\n"
            f"## 변경 목표\n{goals_md}"
            f"## 도메인 규칙\n{_bullet(template.domain_rules)}\n\n"
            f"## 도메인 제약\n{_bullet(template.domain_constraints)}"
        )
    if isinstance(template, FixTemplate):
        problems_md = "\n".join(
            f"- **{p.issue}** -> {p.suggestion}" for p in template.problems
        )
        impl_md = "\n".join(f"{s.step}. {s.todo}" for s in template.implementation)
        return (
            f"## 개요\n{template.about}\n\n"
            f"## 문제 및 제안\n{problems_md}\n\n"
            f"## 구현 단계\n{impl_md}\n\n"
            f"## 도메인 규칙\n{_bullet(template.domain_rules)}\n\n"
            f"## 도메인 제약\n{_bullet(template.domain_constraints)}"
        )
    return template.model_dump_json(indent=2)


def build_github_issue_payload(template: BaseIssueTemplate) -> dict:
    """이슈 템플릿을 GitHub REST API 페이로드로 변환한다."""
    return {
        "title": template.issue_title,
        "body": _format_body(template),
        "labels": [template.label.value],
    }
