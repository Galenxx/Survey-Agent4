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
from src.storage.tool_wrapper import wrap_tool_for_logging
from src.storage.task_storage import TaskStorage


def create_research_gap_crew(task_storage: TaskStorage, papers_dir: str):
    """创建研究 Gap 分析 Crew"""

    papers_dir = os.path.abspath(papers_dir)

    def _make_tools(agent_key: str):
        """Create fresh tool instances wrapped for a specific agent."""
        return [
            wrap_tool_for_logging(SemanticScholarSearchTool(), agent_key, task_storage),
            wrap_tool_for_logging(PdfDownloadTool(output_dir=papers_dir), agent_key, task_storage),
            wrap_tool_for_logging(PdfToTextTool(), agent_key, task_storage),
            wrap_tool_for_logging(RelevanceClassifierTool(), agent_key, task_storage),
            wrap_tool_for_logging(MethodExtractorTool(), agent_key, task_storage),
            wrap_tool_for_logging(GapIdentifierTool(), agent_key, task_storage),
            wrap_tool_for_logging(ReportWriterTool(), agent_key, task_storage),
        ]

    # Wrap tools for each agent so their executions are logged to the correct agent's log file
    router_tools       = _make_tools("router")
    searcher_tools    = _make_tools("searcher")
    filter_tools      = _make_tools("filter")
    analyzer_tools    = _make_tools("analyzer")
    synthesizer_tools = _make_tools("synthesizer")

    manager = create_manager_agent()
    router = create_router_agent(tools=router_tools)
    searcher = create_searcher_agent(tools=searcher_tools)
    filter_agent = create_filter_agent(tools=filter_tools)
    analyzer = create_analyzer_agent(tools=analyzer_tools)
    synthesizer = create_synthesizer_agent(tools=synthesizer_tools)

    router_task = Task(
        description="""分析用户的研究需求，生成结构化的搜索查询。

用户输入: {user_input}

请理解用户意图，提取以下信息并以 JSON 格式输出：
{{
  "topic": "研究主题（从用户输入中提取的核心研究主题，用于后续 gap 分析）",
  "search_query": "用于论文检索的搜索关键词（提取或生成最能代表用户研究意图的英文搜索词，以便在论文数据库中检索）",
  "gap_direction": "用户指定的 gap 类型（如果有，例如 Methodological Gap，否则为空字符串）",
  "time_range": "时间范围，如 2022-2026（默认2020-）",
  "max_results": 最大检索数量（默认50）
}}

直接输出纯 JSON，不要有其他内容。""",
        agent=router,
        expected_output="结构化 JSON 格式的 SearchQuery",
    )

    searcher_task = Task(
        description="""根据搜索查询执行论文检索。

请使用 semantic_scholar_search 工具搜索相关论文。
搜索词: {search_query}
使用 year_range="{time_range}" 只搜索指定时间范围内的论文。
最多搜索 {max_results} 篇（工具会自动只返回有 PDF 的论文）。

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

研究主题: {topic}

1. 对搜索结果中的每篇论文，使用 classify_relevance 工具判断相关性
2. 筛选出与研究主题相关的论文（至少10篇）
3. 返回相关论文列表

请使用 classify_relevance 工具逐篇评估论文相关性。""",
        agent=filter_agent,
        expected_output="筛选后的相关论文列表",
        context=[searcher_task],
    )

    analyzer_task = Task(
        description="""分析论文中的研究 gap。

研究主题: {topic}
gap 分析重点: {gap_direction}（如果用户指定了，则重点分析该类型，否则分析所有六类 gap）

对于筛选出的相关论文：
1. 使用 pdf_to_text 工具提取论文文本（前10页），PDF 文件在 {papers_dir} 目录下
2. 使用 identify_gap 工具识别 gap
3. 返回每篇论文的 gap 分析结果

请使用 pdf_to_text 和 identify_gap 工具分析每篇论文的 gap。""",
        agent=analyzer,
        expected_output="论文 gap 分析结果列表",
        context=[filter_task],
    )

    synthesizer_task = Task(
        description="""汇总所有 gap 分析结果，生成研究报告。

研究主题: {topic}

1. 读取所有论文的 gap 分析结果
2. 按 gap 类型分类汇总
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

        task_storage.log("manager", "SYSTEM", f"Starting analysis for: {user_input}")

        crew = create_research_gap_crew(task_storage, papers_dir)
        result = crew.kickoff(inputs={
            "user_input": user_input,
            "report_path": task_storage.get_report_path(),
            "papers_dir": papers_dir,
            # Template vars for downstream tasks (will be overridden by router output)
            "topic": user_input,
            "search_query": user_input,
            "gap_direction": "",
            "time_range": "2020-",
            "max_results": "50",
        })

        task_storage.log("manager", "SYSTEM", "Analysis workflow completed successfully. Full report saved to report.md.")
        task_storage.complete(summary=str(result)[:500])

        return {
            "status": "success",
            "result": str(result),
            "task_id": task_storage.task_id,
            "report_path": task_storage.get_report_path(),
        }

    except Exception as e:
        import traceback
        task_storage.log("manager", "ERROR", f"Analysis failed: {str(e)}\n{traceback.format_exc()}")
        task_storage.fail(str(e))
        return {
            "status": "failed",
            "error": str(e),
            "task_id": task_storage.task_id,
        }
