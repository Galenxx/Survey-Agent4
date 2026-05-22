"""论文相关性分类工具"""
import json
from typing import Any, Dict
from crewai.tools import BaseTool
from pydantic import Field
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion


class RelevanceClassifierTool(BaseTool):
    """使用 LLM 判断论文与研究主题的相关性，返回完整论文元数据（含 pdf_path）"""

    name: str = "classify_relevance"
    description: str = (
        "判断论文是否与研究主题相关。传入完整论文元数据（id、title、authors、year、abstract、pdf_path 等），"
        "返回论文元数据 + 相关性判断结果（JSON 格式）。"
    )

    def _run(
        self,
        paper_title: str,
        paper_abstract: str,
        research_topic: str,
        paper_id: str = "",
        arxiv_id: str = "",
        authors: str = "",
        year: str = "",
        pdf_path: str = "",
        pdf_url: str = "",
        source: str = "",
        citation_count: int = 0,
        **kwargs: Any,
    ) -> str:
        """
        判断论文相关性，同时原样返回论文完整元数据

        Args:
            paper_title: 论文标题
            paper_abstract: 论文摘要
            research_topic: 研究主题描述
            paper_id: 论文 ID
            arxiv_id: arXiv ID
            authors: 作者（字符串格式）
            year: 发表年份
            pdf_path: PDF 本地路径
            pdf_url: PDF 下载链接
            source: 来源（semantic_scholar 或 arxiv）
            citation_count: 引用数

        Returns:
            JSON: 包含完整论文元数据 + 相关性判断结果
        """
        llm = OpenAICompatibleCompletion(
            model="deepseek-v4-pro",
            provider="deepseek",
            extra_body={"thinking": {"type": "disabled"}},
            temperature=0,
        )

        prompt = f"""你是一个学术论文筛选专家。判断以下论文是否与研究主题相关。

研究主题: {research_topic}

论文标题: {paper_title}

论文摘要: {paper_abstract}

请返回一个 JSON 对象，格式如下：
{{
  "relevant": true 或 false,
  "reason": "简要说明判断理由（1-2句话）"
}}

只返回 JSON，不要有其他内容。"""

        try:
            result_text = llm.call(prompt)

            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            result = json.loads(result_text.strip())

            # 合并论文元数据 + 相关性判断结果，原样返回
            output: Dict[str, Any] = {
                "id": paper_id,
                "arxiv_id": arxiv_id,
                "title": paper_title,
                "authors": authors,
                "year": year,
                "abstract": paper_abstract,
                "pdf_path": pdf_path,
                "pdf_url": pdf_url,
                "source": source,
                "citation_count": citation_count,
                "relevant": result.get("relevant", False),
                "relevance_reason": result.get("reason", ""),
            }
            return json.dumps(output, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "id": paper_id,
                "arxiv_id": arxiv_id,
                "title": paper_title,
                "authors": authors,
                "year": year,
                "abstract": paper_abstract,
                "pdf_path": pdf_path,
                "pdf_url": pdf_url,
                "source": source,
                "citation_count": citation_count,
                "relevant": False,
                "relevance_reason": f"Error: {str(e)}",
            }, ensure_ascii=False, indent=2)
