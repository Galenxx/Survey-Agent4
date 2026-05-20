"""Test Searcher Agent and arXiv search"""
import pytest
from unittest.mock import patch, MagicMock


class TestSearcherAgent:
    """测试 Searcher Agent 的检索功能"""

    @patch("src.agents.searcher_agent.ChatOpenAI")
    def test_searcher_agent_creation(self, mock_llm):
        """测试 Searcher Agent 创建"""
        from src.agents.searcher_agent import create_searcher_agent
        agent = create_searcher_agent()
        assert agent is not None
        assert "Searcher" in agent.role

    @patch("src.tools.arxiv_search.arxiv.Client")
    def test_arxiv_search_tool(self, mock_client):
        """测试 arXiv 搜索工具"""
        from src.tools.arxiv_search import ArxivSearchTool

        mock_result = MagicMock()
        mock_result.entry_id = "http://arxiv.org/abs/2301.12345"
        mock_result.title = "Test Paper"
        mock_result.authors = [MagicMock(__str__=lambda x: "Author")]
        mock_result.summary = "Test abstract"
        mock_result.published = MagicMock(strftime=lambda fmt: "2024-01-01")
        mock_result.updated = MagicMock(strftime=lambda fmt: "2024-01-01")
        mock_result.categories = ["cs.AI"]
        mock_result.pdf_url = "https://arxiv.org/pdf/2301.12345.pdf"

        mock_client.return_value.results.return_value = [mock_result]

        tool = ArxivSearchTool()
        result = tool._run(query="test", max_results=10)

        assert "Test Paper" in result
        assert "2301.12345" in result


class TestArxivDownload:
    """测试 arXiv 下载功能"""

    @patch("src.tools.arxiv_download.arxiv.Client")
    def test_download_tool_creation(self, mock_client):
        """测试下载工具创建"""
        from src.tools.arxiv_download import ArxivDownloadTool
        tool = ArxivDownloadTool(output_dir="test_dir")
        assert tool.output_dir == "test_dir"
