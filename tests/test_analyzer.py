"""Test Analyzer Agent gap identification"""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestAnalyzerAgent:
    """测试 Analyzer Agent 的 Gap 识别功能"""

    @patch("src.agents.analyzer_agent.ChatOpenAI")
    def test_analyzer_agent_creation(self, mock_llm):
        """测试 Analyzer Agent 创建"""
        from src.agents.analyzer_agent import create_analyzer_agent
        agent = create_analyzer_agent()
        assert agent is not None
        assert "Analyzer" in agent.role

    @patch("src.tools.identify_gap.ChatOpenAI")
    def test_gap_identifier_with_direction(self, mock_llm):
        """测试指定方向的 Gap 识别"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "paper_title": "Test Paper",
            "gaps": {
                "Methodological Gap": {
                    "exists": True,
                    "description": "缺少对某方法的系统性评估"
                }
            }
        })
        mock_llm.return_value.invoke.return_value = mock_response

        from src.tools.identify_gap import GapIdentifierTool
        tool = GapIdentifierTool()
        result = tool._run(
            paper_title="Test Paper",
            paper_text="Test content",
            research_topic="LLM in job recommendation",
            gap_direction="Methodological Gap"
        )

        result_json = json.loads(result)
        assert "gaps" in result_json
        assert "Methodological Gap" in result_json["gaps"]

    @patch("src.tools.identify_gap.ChatOpenAI")
    def test_gap_identifier_without_direction(self, mock_llm):
        """测试未指定方向的 Gap 识别（分析全部六类）"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "paper_title": "Test Paper",
            "gaps": {
                "Knowledge Gap": {"exists": True, "description": "..."},
                "Methodological Gap": {"exists": True, "description": "..."},
                "Evidence Gap": {"exists": False, "description": "..."},
                "Population Gap": {"exists": True, "description": "..."},
                "Theoretical Gap": {"exists": False, "description": "..."},
                "Contextual/Time Gap": {"exists": True, "description": "..."},
            }
        })
        mock_llm.return_value.invoke.return_value = mock_response

        from src.tools.identify_gap import GapIdentifierTool
        tool = GapIdentifierTool()
        result = tool._run(
            paper_title="Test Paper",
            paper_text="Test content",
            research_topic="LLM in job recommendation",
            gap_direction=""
        )

        result_json = json.loads(result)
        assert len(result_json["gaps"]) == 6


class TestGapTaxonomy:
    """测试 Gap 分类体系"""

    def test_gap_types_definitions(self):
        """测试六类 Gap 定义"""
        from src.prompts.gap_taxonomy import GAP_TYPES

        assert len(GAP_TYPES) == 6
        assert "Knowledge Gap" in GAP_TYPES
        assert "Methodological Gap" in GAP_TYPES
        assert "Evidence Gap" in GAP_TYPES
        assert "Population Gap" in GAP_TYPES
        assert "Theoretical Gap" in GAP_TYPES
        assert "Contextual/Time Gap" in GAP_TYPES

    def test_get_gap_prompt_with_direction(self):
        """测试获取指定方向的 prompt"""
        from src.prompts.gap_taxonomy import get_gap_prompt

        prompt = get_gap_prompt("Methodological Gap")
        assert "Methodological Gap" in prompt
        assert "方法论空白" in prompt

    def test_get_gap_prompt_without_direction(self):
        """测试获取全部 gap 的 prompt"""
        from src.prompts.gap_taxonomy import get_gap_prompt

        prompt = get_gap_prompt("")
        assert "Knowledge Gap" in prompt
        assert "Methodological Gap" in prompt
        assert "Evidence Gap" in prompt
