"""Searcher Agent"""
from crewai import Agent
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
from typing import Any


def create_searcher_agent(tools: list[Any] | None = None):
    """创建 Searcher Agent（使用 deepseek-chat）"""
    return Agent(
        role="Academic Paper Searcher",
        goal="根据搜索查询在 arXiv 上检索相关论文并下载",
        backstory="你是一个专业的学术论文检索专家，精通 arXiv 等学术数据库的使用。你能够根据不同的研究主题构建有效的搜索策略，找到最相关的高质量论文。",
        verbose=True,
        allow_delegation=False,
        tools=tools,
        llm=OpenAICompatibleCompletion(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
        ),
    )
