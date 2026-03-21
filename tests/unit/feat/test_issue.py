"""FeatTemplate.to_github_body() 테스트."""
from src.domain.feat.models.issue import FeatTemplate


def _make_template(**kwargs) -> FeatTemplate:
    defaults = dict(
        issue_title="[FEAT] x",
        about="about text",
        goal="goal text",
        new_features=["feature one", "feature two"],
        domain_rules=["rule one"],
        additional_info="",
    )
    defaults.update(kwargs)
    return FeatTemplate(**defaults)


def test_to_github_body_contains_about():
    t = _make_template()
    assert "about text" in t.to_github_body()


def test_to_github_body_contains_goal():
    t = _make_template()
    body = t.to_github_body()
    assert "## 목표" in body
    assert "goal text" in body


def test_to_github_body_contains_features():
    t = _make_template()
    body = t.to_github_body()
    assert "## 새로운 기능" in body
    assert "feature one" in body


def test_to_github_body_skips_empty_additional_info():
    t = _make_template(additional_info="")
    body = t.to_github_body()
    assert "## 추가사항" not in body


def test_to_github_body_includes_additional_info_when_present():
    t = _make_template(additional_info="extra info here")
    body = t.to_github_body()
    assert "## 추가사항" in body
    assert "extra info here" in body


def test_to_github_payload_has_required_keys():
    t = _make_template()
    payload = t.to_github_payload()
    assert "title" in payload
    assert "body" in payload
    assert "labels" in payload
    assert payload["title"] == "[FEAT] x"
    assert payload["labels"] == ["feat"]
