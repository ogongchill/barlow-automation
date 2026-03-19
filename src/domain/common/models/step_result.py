"""Step 흐름 제어 시그널."""

from enum import Enum


class ControlSignal(str, Enum):
    CONTINUE = "continue"
    WAIT_FOR_USER = "wait_for_user"
    STOP = "stop"
