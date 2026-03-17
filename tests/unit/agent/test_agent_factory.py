"""AgentFactory tests -- patch Agent SDK and MCP dependencies."""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _patch_deps():
    """Patch Agent and GitHubMCPFactory for all tests in this module."""
    with (
        patch("src.agent.agent_factory.Agent") as mock_agent_cls,
        patch("src.agent.agent_factory.GitHubMCPFactory") as mock_mcp,
    ):
        mock_mcp.readProjectTree.return_value = MagicMock(name="tree_mcp")
        mock_mcp.readProject.return_value = MagicMock(name="files_mcp")
        mock_agent_cls.return_value = MagicMock(name="sdk_agent_instance")
        yield mock_agent_cls, mock_mcp


class TestRelevantBcFinder:

    def test_bc_finder_uses_tree_mcp(self, _patch_deps) -> None:
        mock_agent_cls, mock_mcp = _patch_deps
        from src.agent.agent_factory import AgentFactory

        agent = AgentFactory.relevant_bc_finder()
        mock_mcp.readProjectTree.assert_called()


class TestIssueGen:

    @pytest.mark.parametrize("subcommand", ["feat", "refactor", "fix"])
    def test_issue_gen_selects_correct_key(self, subcommand, _patch_deps) -> None:
        mock_agent_cls, mock_mcp = _patch_deps
        from src.agent.agent_factory import AgentFactory

        agent = AgentFactory.issue_gen(subcommand)
        assert agent is not None
        mock_mcp.readProject.assert_called()

    def test_invalid_subcommand_raises_key_error(self, _patch_deps) -> None:
        from src.agent.agent_factory import AgentFactory

        with pytest.raises(KeyError):
            AgentFactory.issue_gen("invalid")


class TestReissueGen:

    @pytest.mark.parametrize("subcommand", ["feat", "refactor", "fix"])
    def test_reissue_gen_selects_correct_key(self, subcommand, _patch_deps) -> None:
        mock_agent_cls, mock_mcp = _patch_deps
        from src.agent.agent_factory import AgentFactory

        agent = AgentFactory.reissue_gen(subcommand)
        assert agent is not None
        mock_mcp.readProject.assert_called()

    def test_invalid_subcommand_raises_key_error(self, _patch_deps) -> None:
        from src.agent.agent_factory import AgentFactory

        with pytest.raises(KeyError):
            AgentFactory.reissue_gen("invalid")
