"""feat_issue workflow definition 완결성 테스트."""

from src.domain.common.models.step_result import ControlSignal
from src.domain.feat.definition import GRAPH, FIRST_STEP, RESUME_MAP


def test_first_step_in_graph():
    assert FIRST_STEP in GRAPH


def test_graph_all_continue_targets_exist():
    for name, node in GRAPH.items():
        if node.on_continue:
            assert node.on_continue in GRAPH, (
                f"step '{name}' on_continue='{node.on_continue}' not in GRAPH"
            )


def test_resume_map_targets_exist():
    for action, step_name in RESUME_MAP.items():
        assert step_name in GRAPH, (
            f"RESUME_MAP['{action}']='{step_name}' not in GRAPH"
        )


def test_resume_map_has_required_actions():
    assert "accept" in RESUME_MAP
    assert "reject" in RESUME_MAP
    assert "drop_restart" in RESUME_MAP


def test_graph_wait_node_signal_is_wait_for_user():
    node = GRAPH.get("wait_confirmation")
    assert node is not None
    assert node.control_signal == ControlSignal.WAIT_FOR_USER


def test_graph_create_issue_node_signal_is_stop():
    node = GRAPH.get("create_github_issue")
    assert node is not None
    assert node.control_signal == ControlSignal.STOP


def test_graph_all_nodes_have_step_and_mappers():
    for name, node in GRAPH.items():
        assert node.step is not None, f"'{name}' has no step"
        assert callable(node.extract_input), f"'{name}' missing extract_input"
        assert callable(node.apply_output), f"'{name}' missing apply_output"
