"""Router Agent"""
from crewai import Agent
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
from typing import Any


def create_router_agent(tools: list[Any] | None = None, llm=None):
    """Create Router Agent (uses deepseek-v4-pro, thinking disabled)."""
    if llm is None:
        llm = OpenAICompatibleCompletion(
            model="deepseek-v4-pro",
            provider="deepseek",
            extra_body={"thinking": {"type": "disabled"}},
            temperature=0,
        )
    return Agent(
        role="Research Query Router",
        goal="将用户自然语言需求转化为结构化的搜索查询",
        backstory="你是一个专业的学术研究助手，擅长理解用户的研究意图，并将其分解为精确的搜索关键词和参数。你对各个研究领域有广泛了解，能够准确把握研究主题和方向。",
        verbose=True,
        allow_delegation=False,
        tools=tools,
        llm=llm,
    )
