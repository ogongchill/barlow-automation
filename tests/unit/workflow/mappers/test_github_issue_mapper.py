"""GitHub issue mapper 단위 테스트."""

from src.workflow.mappers.github_issue_mapper import build_github_issue_payload


def test_payload_includes_title(feat_template):
    payload = build_github_issue_payload(feat_template)
    assert feat_template.issue_title in payload["title"]


def test_payload_includes_label(feat_template):
    payload = build_github_issue_payload(feat_template)
    assert "feat" in payload.get("labels", [])


def test_payload_body_is_markdown(feat_template):
    payload = build_github_issue_payload(feat_template)
    assert isinstance(payload["body"], str)
    assert len(payload["body"]) > 0


def test_refactor_payload_label(refactor_template):
    payload = build_github_issue_payload(refactor_template)
    assert "refactor" in payload["labels"]


def test_refactor_payload_body_contains_goals(refactor_template):
    payload = build_github_issue_payload(refactor_template)
    assert "As-Is" in payload["body"]
    assert "To-Be" in payload["body"]


def test_fix_payload_label(fix_template):
    payload = build_github_issue_payload(fix_template)
    assert "fix" in payload["labels"]


def test_fix_payload_body_contains_problems(fix_template):
    payload = build_github_issue_payload(fix_template)
    assert "문제 및 제안" in payload["body"]
    assert "구현 단계" in payload["body"]
