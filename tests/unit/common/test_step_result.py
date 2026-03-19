"""StepResult 기본 동작 테스트."""
from src.domain.common.models.step_result import StepResult


def test_default_control_signal_is_continue():
    r = StepResult(status="success")
    assert r.control_signal == "continue"


def test_state_patch_default_empty():
    r = StepResult(status="success")
    assert r.state_patch == {}


def test_wait_for_user_signal():
    r = StepResult(status="waiting", control_signal="wait_for_user")
    assert r.control_signal == "wait_for_user"


def test_stop_signal():
    r = StepResult(status="success", control_signal="stop")
    assert r.control_signal == "stop"


def test_state_patch_stored():
    r = StepResult(status="success", state_patch={"bc_candidates": "{}"})
    assert r.state_patch["bc_candidates"] == "{}"


def test_next_step_default_none():
    r = StepResult(status="success")
    assert r.next_step is None
