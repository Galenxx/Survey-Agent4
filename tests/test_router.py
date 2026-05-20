"""Test Router Agent query decomposition"""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestRouterAgent:
    """测试 Router Agent 的查询分解功能"""

    def test_search_query_structure(self, sample_search_query):
        """测试 SearchQuery 数据结构"""
        assert "topic" in sample_search_query
        assert "direction" in sample_search_query
        assert "gap_direction" in sample_search_query
        assert "time_range" in sample_search_query
        assert "max_results" in sample_search_query

    def test_search_query_with_gap_direction(self, sample_search_query):
        """测试指定 gap 方向的查询"""
        assert sample_search_query["gap_direction"] == "Methodological Gap"
        assert sample_search_query["topic"] == "LLM in job recommendation"

    def test_search_query_without_gap_direction(self):
        """测试未指定 gap 方向的查询"""
        query = {
            "topic": "LLM in job recommendation",
            "direction": "",
            "gap_direction": "",
            "time_range": "2022-2026",
            "max_results": 50,
        }
        assert query["gap_direction"] == ""

    @patch("src.agents.router_agent.ChatOpenAI")
    def test_router_llm_call(self, mock_llm):
        """测试 Router Agent 调用 LLM"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "topic": "LLM in job recommendation",
            "direction": "methodological",
            "gap_direction": "Methodological Gap",
            "time_range": "2022-2026",
            "max_results": 50,
        })
        mock_llm.return_value.invoke.return_value = mock_response

        from src.agents.router_agent import create_router_agent
        agent = create_router_agent()
        assert agent is not None
        assert "Router" in agent.role
