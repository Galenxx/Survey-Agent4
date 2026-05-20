"""Synthesizer Agent"""
from crewai import Agent
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
from typing import Any


def create_synthesizer_agent(tools: list[Any] | None = None):
    """创建 Synthesizer Agent（使用 deepseek-chat）"""
    return Agent(
        role="Research Report Synthesizer",
        goal="汇总 gap 分析结果，生成结构化的 Markdown 研究报告",
        backstory="你是一个专业的学术写作专家，擅长将复杂的研究发现组织成清晰、有逻辑的报告。你能够从大量论文中提炼关键信息，形成有价值的研究洞察。",
        verbose=True,
        allow_delegation=False,
        tools=tools,
        llm=OpenAICompatibleCompletion(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
        ),
    )
