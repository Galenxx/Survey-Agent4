"""Gap 识别工具"""
import json
from crewai.tools import BaseTool
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion


GAP_TYPES = {
    "Knowledge Gap": "知识空白：现有研究未覆盖的基础性问题、概念或理论框架",
    "Methodological Gap": "方法论空白：现有方法在该领域的局限性、缺失的方法或技术",
    "Evidence Gap": "证据空白：缺乏实证研究、实验验证或大规模数据支撑",
    "Population Gap": "人群空白：研究对象或样本的局限，未覆盖特定人群或场景",
    "Theoretical Gap": "理论空白：缺乏理论框架、概念模型或统一的研究范式",
    "Contextual/Time Gap": "情境/时间空白：研究场景过时、未考虑新环境或时效性问题",
}


class GapIdentifierTool(BaseTool):
    """识别论文中的研究 gap"""

    name: str = "identify_gap"
    description: str = "根据 gap_direction 参数识别论文中的研究空白，可指定方向或全部分析"

    def _run(
        self,
        paper_title: str,
        paper_text: str,
        research_topic: str,
        gap_direction: str = "",
        paper_authors: str = "",
        paper_year: str = "",
    ) -> str:
        """
        识别 gap

        Args:
            paper_title: 论文标题
            paper_text: 论文文本
            research_topic: 研究主题
            gap_direction: 指定要分析的 gap 类型，为空则分析全部六类
            paper_authors: 论文作者列表（字符串）
            paper_year: 论文发表年份

        Returns:
            JSON 格式的 gap 分析结果
        """
        llm = OpenAICompatibleCompletion(
            model="deepseek-v4-pro",
            provider="deepseek",
            extra_body={"thinking": {"type": "disabled"}},
            temperature=0,
        )

        if gap_direction:
            gap_types_to_analyze = {gap_direction: GAP_TYPES.get(gap_direction, gap_direction)}
            gap_types_str = f"***{gap_direction}***: {GAP_TYPES.get(gap_direction, gap_direction)}"
            json_example = f'"{gap_direction}": {{"exists": true/false, "description": "描述"}}'
        else:
            gap_types_to_analyze = GAP_TYPES
            gap_types_str = "\n".join([f"***type***: {desc}" for type_, desc in GAP_TYPES.items()])
            json_example = (
                '"Knowledge Gap": {"exists": true/false, "description": "描述"},\n'
                '    "Methodological Gap": {"exists": true/false, "description": "描述"},\n'
                '    "Evidence Gap": {"exists": true/false, "description": "描述"},\n'
                '    "Theoretical Gap": {"exists": true/false, "description": "描述"},\n'
                '    "Population Gap": {"exists": true/false, "description": "描述"},\n'
                '    "Contextual/Time Gap": {"exists": true/false, "description": "描述"}}'
            )

        scope_note = f"请仅分析以下这一类 gap：{gap_types_str}" if gap_direction else f"请分析以下六类 gap：{gap_types_str}"
        json_note = "返回 JSON 格式（只包含指定的 gap 类型）：" if gap_direction else "返回 JSON 格式（包含所有 gap 类型）："

        prompt = f"""你是一个学术研究 gap 分析专家。分析以下论文在研究主题下的空白（gap）。

研究主题: {research_topic}

论文标题: {paper_title}
论文作者: {paper_authors if paper_authors else "未提供"}
论文年份: {paper_year if paper_year else "未提供"}

论文内容:
{paper_text[:8000]}

{scope_note}

对于每类 gap，判断该论文是否存在此类 gap。如果存在，给出具体描述；如果不存在，说明原因。

{json_note}
{{
  "paper_title": "{paper_title}",
  "paper_authors": "{paper_authors if paper_authors else ''}",
  "paper_year": "{paper_year if paper_year else ''}",
  "gaps": {{
    {json_example}
  }}
}}

只返回 JSON，不要有其他内容。必须确保 paper_authors 和 paper_year 字段与输入保持一致。"""

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
