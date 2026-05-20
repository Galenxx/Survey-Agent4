"""Research Gap Crew - 研究 Gap 分析工作流"""
import os
from crewai import Crew, Task, Agent
from typing import List, Dict, Any

from src.agents.manager_agent import create_manager_agent
from src.agents.router_agent import create_router_agent
from src.agents.searcher_agent import create_searcher_agent
from src.agents.filter_agent import create_filter_agent
from src.agents.analyzer_agent import create_analyzer_agent
from src.agents.synthesizer_agent import create_synthesizer_agent
from src.tools import (
    SemanticScholarSearchTool,
    PdfDownloadTool,
    PdfToTextTool,
    RelevanceClassifierTool,
    MethodExtractorTool,
    GapIdentifierTool,
    ReportWriterTool,
)
from src.storage.task_storage import TaskStorage


def create_research_gap_crew(task_storage: TaskStorage, papers_dir: str):
    """创建研究 Gap 分析 Crew"""

    papers_dir = os.path.abspath(papers_dir)
    tools = [
        SemanticScholarSearchTool(),
        PdfDownloadTool(output_dir=papers_dir),
        PdfToTextTool(),
        RelevanceClassifierTool(),
        MethodExtractorTool(),
        GapIdentifierTool(),
        ReportWriterTool(),
    ]

    manager = create_manager_agent()
    router = create_router_agent(tools=tools)
    searcher = create_searcher_agent(tools=tools)
    filter_agent = create_filter_agent(tools=tools)
    analyzer = create_analyzer_agent(tools=tools)
    synthesizer = create_synthesizer_agent(tools=tools)

    router_task = Task(
        description="""分析用户的研究需求，生成结构化的搜索查询。

用户输入: {user_input}

请理解用户意图，提取以下信息并以 JSON 格式输出：
{{
  "topic": "研究主题",
  "direction": "研究方向",
  "gap_direction": "用户指定的 gap 类型（如果有，否则为空字符串）",
  "time_range": "时间范围，如 2022-2026",
  "max_results": 最大检索数量（默认50）
}}

直接输出纯 JSON，不要有其他内容。""",
        agent=router,
        expected_output="结构化 JSON 格式的 SearchQuery",
    )

    searcher_task = Task(
        description="""根据搜索查询执行论文检索。

请使用 semantic_scholar_search 工具搜索与 "LLM in job recommendation" 相关的论文。
搜索词建议使用：large language model job recommendation 或 LLM personalized job matching
使用 year_range="2022-" 只搜索 2022 年之后的论文。
最多搜索 50 篇（工具会自动只返回有 PDF 的论文）。

搜索返回后，对每篇论文：
1. 检查是否有 pdf_url（来自 Semantic Scholar 的 openAccessPdf）
2. 使用 pdf_download 工具下载 PDF（参数：pdf_url=论文的pdf_url, paper_id=论文的arxiv_id或s2_id）
3. 如果下载成功（返回文件路径），返回论文信息 + 下载路径
4. 如果下载失败（返回错误信息），仍返回论文信息但注明下载失败

请将下载的论文 PDF 保存到目录: {papers_dir}

最后返回完整的论文列表（包含 ID、标题、摘要、作者、年份、引用量、PDF 路径等）。""",
        agent=searcher,
        expected_output="论文列表，包含论文 ID、标题、摘要、作者、发布日期等",
        context=[router_task],
    )

    filter_task = Task(
        description="""评估论文与研究主题的相关性。

1. 对搜索结果中的每篇论文，使用 classify_relevance 工具判断相关性
2. 筛选出与 "LLM in job recommendation" 主题相关的论文（至少10篇）
3. 返回相关论文列表

请使用 classify_relevance 工具逐篇评估论文相关性。""",
        agent=filter_agent,
        expected_output="筛选后的相关论文列表",
        context=[searcher_task],
    )

    analyzer_task = Task(
        description="""分析论文中的研究 gap。

对于筛选出的相关论文：
1. 使用 pdf_to_text 工具提取论文文本（前10页），PDF 文件在 {papers_dir} 目录下
2. 使用 identify_gap 工具识别 gap（重点关注 Methodological Gap）
3. 返回每篇论文的 gap 分析结果

研究主题: LLM in job recommendation
gap 分析重点: Methodological Gap（方法论空白）

请使用 pdf_to_text 和 identify_gap 工具分析每篇论文的 gap。""",
        agent=analyzer,
        expected_output="论文 gap 分析结果列表",
        context=[filter_task],
    )

    synthesizer_task = Task(
        description="""汇总所有 gap 分析结果，生成研究报告。

1. 读取所有论文的 gap 分析结果
2. 按 gap 类型（特别是 Methodological Gap）分类汇总
3. 生成结构化的 Markdown 报告

请使用 write_report 工具将分析结果写入报告文件：{report_path}""",
        agent=synthesizer,
        expected_output="Markdown 格式的研究报告",
        context=[analyzer_task],
    )

    crew = Crew(
        agents=[manager, router, searcher, filter_agent, analyzer, synthesizer],
        tasks=[router_task, searcher_task, filter_task, analyzer_task, synthesizer_task],
        manager_agent=manager,
        verbose=True,
    )

    return crew


def run_research_gap_analysis(
    user_input: str,
    task_storage: TaskStorage,
) -> Dict[str, Any]:
    """运行研究 Gap 分析"""
    try:
        papers_dir = os.path.abspath(task_storage.get_papers_dir())

        task_storage.log("manager", f"Starting analysis for: {user_input}")

        crew = create_research_gap_crew(task_storage, papers_dir)
        result = crew.kickoff(inputs={
            "user_input": user_input,
            "report_path": task_storage.get_report_path(),
            "papers_dir": papers_dir,
        })

        task_storage.log("manager", f"Analysis completed: {result}")

        task_storage.complete(summary=str(result))

        return {
            "status": "success",
            "result": str(result),
            "task_id": task_storage.task_id,
            "report_path": task_storage.get_report_path(),
        }

    except Exception as e:
        import traceback
        task_storage.log("manager", f"Analysis failed: {str(e)}\n{traceback.format_exc()}")
        task_storage.fail(str(e))
        return {
            "status": "failed",
            "error": str(e),
            "task_id": task_storage.task_id,
        }
