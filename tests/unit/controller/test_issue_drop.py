"""DroppableItem generation and drop_items filtering tests."""

from src.domain.issue_templates import FeatTemplate, RefactorTemplate, FixTemplate
from src.controller.issue_drop import droppable_items, drop_items, DroppableItem


class TestDroppableItemsFeat:

    def test_id_uniqueness(self, feat_template: FeatTemplate) -> None:
        items = droppable_items(feat_template)
        ids = [item.id for item in items]
        assert len(ids) == len(set(ids))

    def test_section_coverage(self, feat_template: FeatTemplate) -> None:
        items = droppable_items(feat_template)
        sections = {item.section for item in items}
        assert sections == {"신규 기능", "도메인 규칙", "기술 제약"}

    def test_id_format(self, feat_template: FeatTemplate) -> None:
        items = droppable_items(feat_template)
        for item in items:
            assert "::" in item.id
            field, idx = item.id.split("::")
            assert field in ("new_features", "domain_rules", "domain_constraints")
            assert idx.isdigit()

    def test_total_count(self, feat_template: FeatTemplate) -> None:
        items = droppable_items(feat_template)
        expected = (
            len(feat_template.new_features)
            + len(feat_template.domain_rules)
            + len(feat_template.domain_constraints)
        )
        assert len(items) == expected


class TestDroppableItemsRefactor:

    def test_goals_present(self, refactor_template: RefactorTemplate) -> None:
        items = droppable_items(refactor_template)
        goal_items = [i for i in items if i.id.startswith("goals::")]
        assert len(goal_items) == len(refactor_template.goals)

    def test_goal_sections(self, refactor_template: RefactorTemplate) -> None:
        items = droppable_items(refactor_template)
        goal_items = [i for i in items if i.id.startswith("goals::")]
        for i, item in enumerate(goal_items):
            assert item.section == f"목표 {i + 1}"


class TestDroppableItemsFix:

    def test_problems_present(self, fix_template: FixTemplate) -> None:
        items = droppable_items(fix_template)
        problem_items = [i for i in items if i.id.startswith("problems::")]
        assert len(problem_items) == len(fix_template.problems)

    def test_implementation_present(self, fix_template: FixTemplate) -> None:
        items = droppable_items(fix_template)
        impl_items = [i for i in items if i.id.startswith("implementation::")]
        assert len(impl_items) == len(fix_template.implementation)


class TestDropItemsFeat:

    def test_removes_correct_item(self, feat_template: FeatTemplate) -> None:
        result = drop_items(feat_template, {"new_features::0"})
        assert len(result.new_features) == len(feat_template.new_features) - 1
        assert feat_template.new_features[0] not in result.new_features

    def test_empty_set_returns_all(self, feat_template: FeatTemplate) -> None:
        result = drop_items(feat_template, set())
        assert result.new_features == feat_template.new_features
        assert result.domain_rules == feat_template.domain_rules
        assert result.domain_constraints == feat_template.domain_constraints

    def test_removes_all_new_features(self, feat_template: FeatTemplate) -> None:
        ids = {f"new_features::{i}" for i in range(len(feat_template.new_features))}
        result = drop_items(feat_template, ids)
        assert result.new_features == []

    def test_domain_rule_removal(self, feat_template: FeatTemplate) -> None:
        result = drop_items(feat_template, {"domain_rules::0"})
        assert len(result.domain_rules) == len(feat_template.domain_rules) - 1


class TestDropItemsRefactor:

    def test_refactor_goal_removal(self, refactor_template: RefactorTemplate) -> None:
        result = drop_items(refactor_template, {"goals::0"})
        assert len(result.goals) == len(refactor_template.goals) - 1


class TestDropItemsFix:

    def test_fix_problem_removal(self, fix_template: FixTemplate) -> None:
        result = drop_items(fix_template, {"problems::0"})
        assert len(result.problems) == len(fix_template.problems) - 1


class TestDroppableReindex:

    def test_after_drop_reindexes_from_zero(self, feat_template: FeatTemplate) -> None:
        dropped = drop_items(feat_template, {"new_features::0"})
        items = droppable_items(dropped)
        feature_items = [i for i in items if i.id.startswith("new_features::")]
        if feature_items:
            assert feature_items[0].id == "new_features::0"
            for idx, item in enumerate(feature_items):
                assert item.id == f"new_features::{idx}"
