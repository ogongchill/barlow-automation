"""domain/issue/entities.py 모델 테스트."""

from src.domain.issue.entities import Label, FeatTemplate


def test_label_values():
    assert Label.FEAT.value == "feat"
    assert Label.REFACTOR.value == "refactor"
    assert Label.FIX.value == "fix"


def test_feat_template_label(feat_template):
    from src.domain.issue.entities import Label
    assert feat_template.label == Label.FEAT


def test_refactor_template_label(refactor_template):
    assert refactor_template.label == Label.REFACTOR


def test_fix_template_label(fix_template):
    assert fix_template.label == Label.FIX
