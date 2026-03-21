"""ControlSignal enum 테스트."""

from src.domain.common.models.step_result import ControlSignal


def test_control_signal_values():
    assert ControlSignal.CONTINUE == "continue"
    assert ControlSignal.WAIT_FOR_USER == "wait_for_user"
    assert ControlSignal.STOP == "stop"


def test_control_signal_is_str():
    assert isinstance(ControlSignal.CONTINUE, str)
