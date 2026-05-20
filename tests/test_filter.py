"""Test Filter Agent relevance classification"""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestFilterAgent:
    """测试 Filter Agent 的相关性筛选功能"""

    @patch("src.agents.filter_agent.ChatOpenAI")
    def test_filter_agent_creation(self, mock_llm):
        """测试 Filter Agent 创建"""
        from src.agents.filter_agent import create_filter_agent
        agent = create_filter_agent()
        assert agent is not None
        assert "Filter" in agent.role

    @patch("src.tools.classify_relevance.ChatOpenAI")
    def test_relevance_classifier_tool(self, mock_llm):
        """测试相关性分类工具"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "relevant": True,
            "reason": "论文主题与研究领域高度相关"
        })
        mock_llm.return_value.invoke.return_value = mock_response

        from src.tools.classify_relevance import RelevanceClassifierTool
        tool = RelevanceClassifierTool()
        result = tool._run(
            paper_title="Test Paper",
            paper_abstract="Test abstract about job recommendation",
            research_topic="LLM in job recommendation"
        )

        result_json = json.loads(result)
        assert result_json["relevant"] is True

    def test_relevance_classifier_handles_invalid_json(self):
        """测试分类工具处理无效 JSON"""
        from src.tools.classify_relevance import RelevanceClassifierTool
        tool = RelevanceClassifierTool()

        with patch("src.tools.classify_relevance.ChatOpenAI") as mock_llm:
            mock_response = MagicMock()
            mock_response.content = "Invalid JSON"
            mock_llm.return_value.invoke.return_value = mock_response

            result = tool._run(
                paper_title="Test",
                paper_abstract="Abstract",
                research_topic="Topic"
            )

            result_json = json.loads(result)
            assert result_json["relevant"] is False
