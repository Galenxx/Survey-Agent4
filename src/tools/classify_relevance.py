"""论文相关性分类工具"""
import json
from crewai.tools import BaseTool
from pydantic import Field
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion


class RelevanceClassifierTool(BaseTool):
    """使用 LLM 判断论文与研究主题的相关性"""

    name: str = "classify_relevance"
    description: str = "判断论文是否与研究主题相关，返回 JSON 格式结果"

    def _run(self, paper_title: str, paper_abstract: str, research_topic: str) -> str:
        """
        判断论文相关性

        Args:
            paper_title: 论文标题
            paper_abstract: 论文摘要
            research_topic: 研究主题描述

        Returns:
            JSON: {"relevant": true/false, "reason": "判断理由"}
        """
        llm = OpenAICompatibleCompletion(
            model="deepseek-chat",
            provider="deepseek",
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
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"relevant": False, "reason": f"Error: {str(e)}"}, ensure_ascii=False)
