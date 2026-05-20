"""六类 Gap 的分类 Prompt 模板"""

GAP_TYPES = {
    "Knowledge Gap": "知识空白：现有研究未覆盖的基础性问题、概念或理论框架",
    "Methodological Gap": "方法论空白：现有方法在该领域的局限性、缺失的方法或技术",
    "Evidence Gap": "证据空白：缺乏实证研究、实验验证或大规模数据支撑",
    "Population Gap": "人群空白：研究对象或样本的局限，未覆盖特定人群或场景",
    "Theoretical Gap": "理论空白：缺乏理论框架、概念模型或统一的研究范式",
    "Contextual/Time Gap": "情境/时间空白：研究场景过时、未考虑新环境或时效性问题",
}


def get_gap_prompt(gap_direction: str = "") -> str:
    """
    获取 gap 分析 prompt

    Args:
        gap_direction: 指定要分析的 gap 类型，为空则返回全部六类

    Returns:
        格式化后的 gap prompt
    """
    if gap_direction:
        desc = GAP_TYPES.get(gap_direction, gap_direction)
        return f"*{gap_direction}*: {desc}"

    return "\n".join([f"*{type_}*: {desc}" for type_, desc in GAP_TYPES.items()])


def get_full_gap_taxonomy() -> dict:
    """获取完整的 gap 分类体系"""
    return GAP_TYPES.copy()
