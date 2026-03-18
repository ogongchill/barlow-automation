"""Slack payload mapper 단위 테스트."""

from src.workflow.mappers.slack_payload_mapper import (
    build_issue_blocks,
    build_bc_decision_blocks,
    build_reject_modal,
    build_drop_modal,
    build_bc_reject_modal,
)
from src.controller.issue_drop import DroppableItem


def test_build_issue_blocks_has_three_buttons(feat_template):
    blocks = build_issue_blocks("U1", feat_template, "")
    action = next(b for b in blocks if b["type"] == "actions")
    ids = [e["action_id"] for e in action["elements"]]
    assert ids == ["issue_accept", "issue_reject", "issue_drop"]


def test_build_issue_blocks_includes_usage_context(feat_template):
    blocks = build_issue_blocks("U1", feat_template, "tokens: 100")
    ctx = [b for b in blocks if b["type"] == "context"]
    assert len(ctx) == 1
    assert "tokens: 100" in ctx[0]["elements"][0]["text"]


def test_build_issue_blocks_no_usage_no_context(feat_template):
    blocks = build_issue_blocks("U1", feat_template, "")
    ctx = [b for b in blocks if b["type"] == "context"]
    assert len(ctx) == 0


def test_build_bc_decision_blocks_has_two_buttons():
    bc_decision_json = (
        '{"primary_context":"OrderContext","rationale":"..",'
        '"mapping_summary":"..","selected_contexts":[],'
        '"validation_points":[],"decision":"reuse_existing",'
        '"new_bc_needed":false,"supporting_contexts":[],"issue_focus":"."}'
    )
    blocks = build_bc_decision_blocks("U1", bc_decision_json, "")
    action = next(b for b in blocks if b["type"] == "actions")
    ids = [e["action_id"] for e in action["elements"]]
    assert "bc_accept" in ids
    assert "bc_reject" in ids


def test_build_bc_decision_blocks_reuse_existing_label():
    bc_decision_json = '{"decision":"reuse_existing","primary_context":"OrderContext","mapping_summary":"ok","selected_contexts":[],"validation_points":[]}'
    blocks = build_bc_decision_blocks(None, bc_decision_json, "")
    section_texts = [b["text"]["text"] for b in blocks if b["type"] == "section"]
    combined = " ".join(section_texts)
    assert "기존 BC 재사용" in combined


def test_build_bc_decision_blocks_new_bc_label():
    bc_decision_json = '{"decision":"new","primary_context":"NewCtx","mapping_summary":"new bc","selected_contexts":[],"validation_points":[]}'
    blocks = build_bc_decision_blocks(None, bc_decision_json, "")
    section_texts = [b["text"]["text"] for b in blocks if b["type"] == "section"]
    combined = " ".join(section_texts)
    assert "신규 BC 제안" in combined


def test_build_bc_decision_blocks_with_usage():
    bc_decision_json = '{"decision":"reuse_existing","primary_context":"X","mapping_summary":"","selected_contexts":[],"validation_points":[]}'
    blocks = build_bc_decision_blocks("U1", bc_decision_json, "cost: $0.01")
    ctx = [b for b in blocks if b["type"] == "context"]
    assert len(ctx) == 1


def test_build_reject_modal_callback_id():
    assert build_reject_modal("ts1", "C1", "U1")["callback_id"] == "reject_submit"


def test_build_reject_modal_has_input_block():
    modal = build_reject_modal("ts1", "C1", "U1")
    assert modal["blocks"][0]["type"] == "input"
    assert modal["blocks"][0]["block_id"] == "additional_requirements"


def test_build_bc_reject_modal_callback_id():
    assert build_bc_reject_modal("ts1", "C1", "U1")["callback_id"] == "bc_reject_submit"


def test_build_bc_reject_modal_has_feedback_block():
    modal = build_bc_reject_modal("ts1", "C1", "U1")
    assert modal["blocks"][0]["block_id"] == "feedback"


def test_build_drop_modal_callback_id():
    items = [DroppableItem(id="f::0", section="기능", text="북마크 추가")]
    modal = build_drop_modal("ts1", "C1", "U1", items)
    assert modal["callback_id"] == "drop_submit"


def test_build_drop_modal_has_options():
    items = [
        DroppableItem(id="f::0", section="기능", text="북마크 추가"),
        DroppableItem(id="f::1", section="기능", text="북마크 삭제"),
    ]
    modal = build_drop_modal("ts1", "C1", "U1", items)
    options = modal["blocks"][0]["element"]["options"]
    assert len(options) == 2
    assert options[0]["value"] == "f::0"
