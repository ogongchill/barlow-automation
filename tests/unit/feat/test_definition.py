"""feat_issue workflow definition 완결성 테스트."""
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


def test_graph_wait_node_has_no_continue():
    wait_node = GRAPH.get("wait_confirmation")
    assert wait_node is not None
    assert wait_node.on_continue is None


def test_graph_create_issue_node_has_stop():
    node = GRAPH.get("create_github_issue")
    assert node is not None
    assert node.on_stop is not None or (node.on_continue is None and node.on_wait is None)
