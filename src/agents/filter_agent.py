"""Filter Agent"""
from crewai import Agent
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
from typing import Any


def create_filter_agent(tools: list[Any] | None = None, llm=None):
    """Create Filter Agent (uses deepseek-v4-pro, function-calling enabled)."""
    if llm is None:
        llm = OpenAICompatibleCompletion(
            model="deepseek-v4-pro",
            provider="deepseek",
            extra_body={"thinking": {"type": "disabled"}},
            temperature=0,
        )
    return Agent(
        role="Paper Relevance Filter",
        goal="评估论文与研究主题的相关性，筛选高质量的相关论文",
        backstory="你是一个严格的学术论文评审专家，对论文的相关性和研究质量有敏锐的判断力。你会仔细阅读每篇论文的摘要，评估其与目标研究主题的契合程度。",
        verbose=True,
        allow_delegation=False,
        tools=tools,
        llm=llm,
        function_calling_llm=llm,
    )
