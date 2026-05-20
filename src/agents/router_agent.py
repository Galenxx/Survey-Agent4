"""Router Agent"""
from crewai import Agent
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
from typing import Any


def create_router_agent(tools: list[Any] | None = None):
    """创建 Router Agent（使用 deepseek-chat）"""
    return Agent(
        role="Research Query Router",
        goal="将用户自然语言需求转化为结构化的搜索查询",
        backstory="你是一个专业的学术研究助手，擅长理解用户的研究意图，并将其分解为精确的搜索关键词和参数。你对各个研究领域有广泛了解，能够准确把握研究主题和方向。",
        verbose=True,
        allow_delegation=False,
        tools=tools,
        llm=OpenAICompatibleCompletion(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
        ),
    )
