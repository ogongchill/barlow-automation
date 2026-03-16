"""Label enum values and template label property tests."""

from src.domain.issue_templates import Label, FeatTemplate, RefactorTemplate, FixTemplate


class TestLabel:

    def test_feat_value(self) -> None:
        assert Label.FEAT.value == "feat"

    def test_refactor_value(self) -> None:
        assert Label.REFACTOR.value == "refactor"

    def test_fix_value(self) -> None:
        assert Label.FIX.value == "fix"

    def test_label_count(self) -> None:
        assert len(Label) == 3


class TestFeatTemplateLabel:

    def test_label_is_feat(self, feat_template: FeatTemplate) -> None:
        assert feat_template.label == Label.FEAT

    def test_label_value(self, feat_template: FeatTemplate) -> None:
        assert feat_template.label.value == "feat"


class TestRefactorTemplateLabel:

    def test_label_is_refactor(self, refactor_template: RefactorTemplate) -> None:
        assert refactor_template.label == Label.REFACTOR

    def test_label_value(self, refactor_template: RefactorTemplate) -> None:
        assert refactor_template.label.value == "refactor"


class TestFixTemplateLabel:

    def test_label_is_fix(self, fix_template: FixTemplate) -> None:
        assert fix_template.label == Label.FIX

    def test_label_value(self, fix_template: FixTemplate) -> None:
        assert fix_template.label.value == "fix"
