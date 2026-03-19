"""build_issue_blocks, build_reject_modal, build_drop_modal tests."""

import json

from src.controller._reply import (
    build_issue_blocks,
    build_reject_modal,
    build_drop_modal,
    _SECTION_LIMIT,
)
from src.controller.issue_drop import droppable_items, DroppableItem
from src.domain.feat.models.issue import FeatTemplate


class TestBuildIssueBlocks:

    def test_has_three_buttons(self, feat_template: FeatTemplate) -> None:
        blocks = build_issue_blocks("U1", feat_template, "")
        actions = [b for b in blocks if b["type"] == "actions"]
        assert len(actions) == 1
        buttons = actions[0]["elements"]
        assert len(buttons) == 3
        action_ids = {b["action_id"] for b in buttons}
        assert action_ids == {"issue_accept", "issue_reject", "issue_drop"}

    def test_no_context_without_usage(self, feat_template: FeatTemplate) -> None:
        blocks = build_issue_blocks("U1", feat_template, "")
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) == 0

    def test_context_with_usage(self, feat_template: FeatTemplate) -> None:
        blocks = build_issue_blocks("U1", feat_template, "in=100 out=50")
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) == 1
        assert "in=100 out=50" in context_blocks[0]["elements"][0]["text"]

    def test_long_text_splits_to_multiple_sections(self, feat_template: FeatTemplate) -> None:
        long_template = feat_template.model_copy(update={
            "about": "A" * (_SECTION_LIMIT + 500),
        })
        blocks = build_issue_blocks(None, long_template, "")
        section_blocks = [b for b in blocks if b["type"] == "section"]
        assert len(section_blocks) >= 2

    def test_mention_when_user_provided(self, feat_template: FeatTemplate) -> None:
        blocks = build_issue_blocks("U_MENTION", feat_template, "")
        section_blocks = [b for b in blocks if b["type"] == "section"]
        first_text = section_blocks[0]["text"]["text"]
        assert "<@U_MENTION>" in first_text

    def test_no_mention_when_user_is_none(self, feat_template: FeatTemplate) -> None:
        blocks = build_issue_blocks(None, feat_template, "")
        section_blocks = [b for b in blocks if b["type"] == "section"]
        first_text = section_blocks[0]["text"]["text"]
        assert "<@" not in first_text


class TestBuildRejectModal:

    def test_callback_id(self) -> None:
        modal = build_reject_modal("ts1", "C1", "U1")
        assert modal["callback_id"] == "reject_submit"

    def test_private_metadata_structure(self) -> None:
        modal = build_reject_modal("ts1", "C1", "U1")
        meta = json.loads(modal["private_metadata"])
        assert meta["message_ts"] == "ts1"
        assert meta["channel_id"] == "C1"
        assert meta["user_id"] == "U1"

    def test_has_input_block(self) -> None:
        modal = build_reject_modal("ts1", "C1", "U1")
        assert len(modal["blocks"]) == 1
        assert modal["blocks"][0]["type"] == "input"


class TestBuildDropModal:

    def test_callback_id(self, feat_template: FeatTemplate) -> None:
        items = droppable_items(feat_template)
        modal = build_drop_modal("ts1", "C1", "U1", items)
        assert modal["callback_id"] == "drop_submit"

    def test_option_count(self, feat_template: FeatTemplate) -> None:
        items = droppable_items(feat_template)
        modal = build_drop_modal("ts1", "C1", "U1", items)
        options = modal["blocks"][0]["element"]["options"]
        assert len(options) == len(items)

    def test_empty_items(self) -> None:
        modal = build_drop_modal("ts1", "C1", "U1", [])
        options = modal["blocks"][0]["element"]["options"]
        assert len(options) == 0

    def test_private_metadata(self, feat_template: FeatTemplate) -> None:
        items = droppable_items(feat_template)
        modal = build_drop_modal("ts1", "C1", "U1", items)
        meta = json.loads(modal["private_metadata"])
        assert meta["message_ts"] == "ts1"
        assert meta["channel_id"] == "C1"
        assert meta["user_id"] == "U1"
