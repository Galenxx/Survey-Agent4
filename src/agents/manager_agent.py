"""Manager Agent（总协调）"""
from crewai import Agent
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
import os
from dotenv import load_dotenv

load_dotenv()


def create_manager_agent(llm=None):
    """创建 Manager Agent（默认使用 GLM-4 协调）"""
    if llm is None:
        llm = OpenAICompatibleCompletion(
            model="glm-5.1",
            provider="dashscope",
            api_key=os.getenv("GLM_API_KEY", ""),
            base_url="https://open.bigmodel.cn/api/paas/v4",
            temperature=0,
        )
    return Agent(
        role="Research Coordination Manager",
        goal="统筹整个研究 gap 分析流程，决定调用策略，确保高效完成分析任务",
        backstory="你是一个经验丰富的学术研究协调者，擅长把复杂的研究需求拆解成具体的执行步骤，并监控整个流程的执行质量。你对机器学习和学术研究有深刻理解，能够准确判断论文的相关性和研究价值。",
        verbose=True,
        allow_delegation=True,
        llm=llm,
    )
