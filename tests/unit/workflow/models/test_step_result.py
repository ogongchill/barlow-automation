"""StepResult 생성 및 control_signal 테스트."""

from src.workflow.models.step_result import StepResult


def test_default_control_signal_is_continue():
    result = StepResult(status="success")
    assert result.control_signal == "continue"


def test_wait_for_user_signal():
    result = StepResult(status="waiting", control_signal="wait_for_user")
    assert result.control_signal == "wait_for_user"


def test_state_patch_default_empty():
    result = StepResult(status="success")
    assert result.state_patch == {}
