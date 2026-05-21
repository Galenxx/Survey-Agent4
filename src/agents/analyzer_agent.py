"""Analyzer Agent"""
from crewai import Agent
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
from typing import Any


def create_analyzer_agent(tools: list[Any] | None = None, llm=None):
    """创建 Analyzer Agent（默认使用 deepseek-chat）"""
    if llm is None:
        llm = OpenAICompatibleCompletion(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
        )
    return Agent(
        role="Research Gap Analyzer",
        goal="识别论文中的研究空白，按六类 gap 进行分类分析",
        backstory="你是一个资深的学术研究员，精通各种研究方法和技术路线。你能够深入分析论文的研究贡献，识别出知识空白、方法论不足、证据缺失等问题，并给出专业的评价。",
        verbose=True,
        allow_delegation=False,
        tools=tools,
        llm=llm,
    )
