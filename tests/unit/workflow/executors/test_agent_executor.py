"""AgentExecutor unit tests -- Phase 4 of test-plan."""

import pytest
from unittest.mock import patch, MagicMock
from src.workflow.executors.agent_executor import AgentExecutor, AgentKey


def test_feat_issue_gen_uses_read_project_mcp():
    with patch("src.workflow.executors.agent_executor.GitHubMCPFactory") as mock_factory, \
         patch("src.workflow.executors.agent_executor.Agent"):
        mock_factory.readProject.return_value = MagicMock()
        AgentExecutor.build(AgentKey.FEAT_ISSUE_GEN)
        mock_factory.readProject.assert_called_once()


def test_relevant_bc_finder_uses_read_tree_mcp():
    with patch("src.workflow.executors.agent_executor.GitHubMCPFactory") as mock_factory, \
         patch("src.workflow.executors.agent_executor.Agent"):
        mock_factory.readProjectTree.return_value = MagicMock()
        AgentExecutor.build(AgentKey.RELEVANT_BC_FINDER)
        mock_factory.readProjectTree.assert_called_once()


def test_invalid_agent_key_raises():
    with pytest.raises((KeyError, ValueError)):
        AgentExecutor.build("unknown_key")


def test_refactor_issue_gen_uses_read_project_mcp():
    with patch("src.workflow.executors.agent_executor.GitHubMCPFactory") as mock_factory, \
         patch("src.workflow.executors.agent_executor.Agent"):
        mock_factory.readProject.return_value = MagicMock()
        AgentExecutor.build(AgentKey.REFACTOR_ISSUE_GEN)
        mock_factory.readProject.assert_called_once()


def test_fix_issue_gen_uses_read_project_mcp():
    with patch("src.workflow.executors.agent_executor.GitHubMCPFactory") as mock_factory, \
         patch("src.workflow.executors.agent_executor.Agent"):
        mock_factory.readProject.return_value = MagicMock()
        AgentExecutor.build(AgentKey.FIX_ISSUE_GEN)
        mock_factory.readProject.assert_called_once()


def test_reissue_gen_keys_use_read_project_mcp():
    for key in (AgentKey.FEAT_REISSUE_GEN, AgentKey.REFACTOR_REISSUE_GEN, AgentKey.FIX_REISSUE_GEN):
        with patch("src.workflow.executors.agent_executor.GitHubMCPFactory") as mock_factory, \
             patch("src.workflow.executors.agent_executor.Agent"):
            mock_factory.readProject.return_value = MagicMock()
            AgentExecutor.build(key)
            mock_factory.readProject.assert_called_once()


def test_build_returns_openai_agent():
    with patch("src.workflow.executors.agent_executor.GitHubMCPFactory") as mock_factory, \
         patch("src.workflow.executors.agent_executor.Agent"):
        mock_factory.readProjectTree.return_value = MagicMock()
        agent = AgentExecutor.build(AgentKey.RELEVANT_BC_FINDER)
        from src.agent.openai import OpenAIAgent
        assert isinstance(agent, OpenAIAgent)
