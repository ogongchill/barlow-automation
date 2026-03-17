"""PendingRecord serialization roundtrip tests."""

import time

from src.domain.issue_templates import FeatTemplate, RefactorTemplate, FixTemplate
from src.domain.pending import PendingRecord, PENDING_TTL_SECONDS


def _make_record(subcommand: str, typed_output) -> PendingRecord:
    return PendingRecord(
        pk="ts_123",
        subcommand=subcommand,
        user_id="U1",
        channel_id="C1",
        user_message="test prompt",
        bc_finder_output="bc finder context",
        typed_output=typed_output,
    )


class TestFeatRoundtrip:

    def test_roundtrip(self, feat_template: FeatTemplate) -> None:
        record = _make_record("feat", feat_template)
        item = record.to_item()
        restored = PendingRecord.from_item(item)
        assert restored.pk == record.pk
        assert restored.subcommand == "feat"
        assert restored.typed_output.issue_title == feat_template.issue_title
        assert restored.typed_output.new_features == feat_template.new_features

    def test_to_item_has_all_keys(self, feat_template: FeatTemplate) -> None:
        record = _make_record("feat", feat_template)
        item = record.to_item()
        expected_keys = {
            "pk", "subcommand", "user_id", "channel_id",
            "user_message", "bc_finder_output", "typed_output", "ttl",
        }
        assert set(item.keys()) == expected_keys

    def test_ttl_is_positive(self, feat_template: FeatTemplate) -> None:
        record = _make_record("feat", feat_template)
        assert record.ttl > 0
        assert record.ttl > int(time.time())


class TestRefactorRoundtrip:

    def test_roundtrip(self, refactor_template: RefactorTemplate) -> None:
        record = _make_record("refactor", refactor_template)
        item = record.to_item()
        restored = PendingRecord.from_item(item)
        assert restored.subcommand == "refactor"
        assert len(restored.typed_output.goals) == 2
        assert restored.typed_output.goals[0].as_is == refactor_template.goals[0].as_is

    def test_to_item_has_all_keys(self, refactor_template: RefactorTemplate) -> None:
        record = _make_record("refactor", refactor_template)
        item = record.to_item()
        assert "typed_output" in item
        assert "ttl" in item


class TestFixRoundtrip:

    def test_roundtrip(self, fix_template: FixTemplate) -> None:
        record = _make_record("fix", fix_template)
        item = record.to_item()
        restored = PendingRecord.from_item(item)
        assert restored.subcommand == "fix"
        assert len(restored.typed_output.problems) == 1
        assert restored.typed_output.problems[0].issue == fix_template.problems[0].issue

    def test_ttl_within_expected_range(self, fix_template: FixTemplate) -> None:
        before = int(time.time()) + PENDING_TTL_SECONDS
        record = _make_record("fix", fix_template)
        after = int(time.time()) + PENDING_TTL_SECONDS
        assert before <= record.ttl <= after
