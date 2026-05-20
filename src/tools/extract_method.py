"""研究方法提取工具"""
import json
from crewai.tools import BaseTool
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion


class MethodExtractorTool(BaseTool):
    """从论文中提取研究方法"""

    name: str = "extract_method"
    description: str = "从论文文本中提取研究方法和技术路线"

    def _run(self, paper_title: str, paper_text: str) -> str:
        """
        提取研究方法

        Args:
            paper_title: 论文标题
            paper_text: 论文文本（前几页）

        Returns:
            JSON 格式的研究方法描述
        """
        llm = OpenAICompatibleCompletion(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
        )

        prompt = f"""你是一个学术研究方法分析专家。从以下论文中提取研究方法。

论文标题: {paper_title}

论文内容（前几页）:
{paper_text[:8000]}

请返回一个 JSON 对象，包含以下字段：
{{
  "methods": ["方法1", "方法2", ...],
  "dataset": "使用的数据集或数据来源",
  "approach": "整体研究路线/技术方案简述",
  "key_techniques": ["关键技术1", "关键技术2", ...]
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

            return result_text.strip()

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
