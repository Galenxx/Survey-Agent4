"""arXiv 搜索工具"""
import time
from typing import List, Dict, Any
from crewai.tools import BaseTool
from pydantic import Field
import arxiv


class ArxivSearchTool(BaseTool):
    """搜索 arXiv 论文"""

    name: str = "arxiv_search"
    description: str = "搜索 arXiv 论文数据库，根据查询词返回相关论文列表"

    def _run(self, query: str, max_results: int = 50, time_range: str = "") -> str:
        """
        执行 arXiv 搜索

        Args:
            query: 搜索查询词
            max_results: 最大返回结果数
            time_range: 时间范围，格式如 "2022-01-01 to 2026-12-31"

        Returns:
            JSON 格式的论文列表
        """
        papers = []
        last_error = ""

        for attempt in range(3):
            try:
                if attempt > 0:
                    wait_time = 15 * attempt
                    time.sleep(wait_time)

                client = arxiv.Client()
                search = arxiv.Search(
                    query=query,
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.Relevance,
                )

                for result in client.results(search):
                    paper_info = {
                        "id": result.entry_id.split("/")[-1],
                        "title": result.title,
                        "authors": [str(author) for author in result.authors],
                        "abstract": result.summary,
                        "published": result.published.strftime("%Y-%m-%d"),
                        "updated": result.updated.strftime("%Y-%m-%d"),
                        "categories": result.categories,
                        "pdf_url": result.pdf_url,
                    }
                    papers.append(paper_info)
                    time.sleep(3)

                import json
                return json.dumps(papers, ensure_ascii=False, indent=2)

            except Exception as e:
                last_error = str(e)
                papers = []

        import json
        return f"Error searching arXiv after 3 attempts: {last_error}"
