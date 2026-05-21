"""Research Gap Crew - 研究 Gap 分析工作流"""
import json
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

# Import from crew_executor (no circular import - crew_executor imports this module inside functions)
from backend.services.crew_executor import parse_router_output, broadcast_event


def create_research_gap_crew(task_storage: TaskStorage, papers_dir: str, skip_router: bool = False):
    """创建研究 Gap 分析 Crew"""

    papers_dir = os.path.abspath(papers_dir)

    def _wrap_tools(agent_key: str, tool_list):
        return [wrap_tool_for_logging(t(output_dir=papers_dir) if t == PdfDownloadTool else t(), agent_key=agent_key, task_storage=task_storage) for t in tool_list]

    router_tools = []
    searcher_tools = _wrap_tools("searcher", [SemanticScholarSearchTool, PdfDownloadTool])
    filter_tools = _wrap_tools("filter", [RelevanceClassifierTool])
    analyzer_tools = _wrap_tools("analyzer", [PdfToTextTool, GapIdentifierTool])
    synthesizer_tools = _wrap_tools("synthesizer", [ReportWriterTool])

    manager = create_manager_agent()
    router = create_router_agent(tools=router_tools)
    searcher = create_searcher_agent(tools=searcher_tools)
    filter_agent = create_filter_agent(tools=filter_tools)
    analyzer = create_analyzer_agent(tools=analyzer_tools)
    synthesizer = create_synthesizer_agent(tools=synthesizer_tools)

    router_task = Task(
        description="""分析用户的研究需求，生成结构化的搜索查询参数。

用户输入: {user_input}

请理解用户意图，从用户输入中提取或生成以下字段，输出为纯 JSON：
{{
  "topic": "研究主题（必填，从用户输入中提取的核心研究主题，用于后续 gap 分析。注意：topic 应该只是研究对象/领域，不要包含 gap 类型方向。例如用户输入「LLM的methodological gap」，topic 应填「Large Language Model」，gap_direction 填「Methodological Gap」）",
  "search_query": "检索关键词（必填，提取或生成最能代表用户研究意图的英文搜索词，不要包含 gap 类型词如「gap」）",
  "gap_direction": "Gap 类型方向（可选，若用户明确指定了 gap 类型则填入，否则使用默认值空字符串 \"\" 表示分析所有类型。可识别的英文关键词包括：methodological/methodology/method → Methodological Gap，knowledge/theory/conceptual → Knowledge Gap，empirical/evidence/experimental → Evidence Gap，theoretical/theory/foundation → Theoretical Gap，population/people/user/group → Population Gap，contextual/temporal/time/context → Contextual/Time Gap。中文关键词同理）",
  "time_range": "年份范围（可选，格式如 \"2022-\" 或 \"2020-2026\"，若用户未指定则使用默认值 \"2020-\"）",
  "max_results": 最大检索数量（可选，整数，若用户未指定则使用默认值 50）
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

    tasks = [router_task, searcher_task, filter_task, analyzer_task, synthesizer_task]
    agents = [manager, router, searcher, filter_agent, analyzer, synthesizer]
    if skip_router:
        tasks = [searcher_task, filter_task, analyzer_task, synthesizer_task]
        agents = [manager, searcher, filter_agent, analyzer, synthesizer]

    crew = Crew(
        agents=agents,
        tasks=tasks,
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
        from dotenv import load_dotenv
        from pathlib import Path

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")

        papers_dir = os.path.abspath(task_storage.get_papers_dir())

        task_storage.log("manager", "SYSTEM", f"Starting analysis for: {user_input}")

        # Default inputs - will be overridden by router output
        default_inputs = {
            "user_input": user_input,
            "report_path": task_storage.get_report_path(),
            "papers_dir": papers_dir,
            "topic": user_input,
            "search_query": user_input,
            "gap_direction": "",
            "time_range": "2020-",
            "max_results": "50",
        }

        # Step 1: Run Router Agent independently to parse user input
        task_storage.log("manager", "SYSTEM", "Step 1: Running Router Agent to parse user input...")
        from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion

        router_llm = OpenAICompatibleCompletion(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
        )

        router_prompt = f"""分析用户的研究需求，生成结构化的搜索查询参数。

用户输入: {user_input}

请理解用户意图，从用户输入中提取或生成以下字段，输出为纯 JSON：
{{
  "topic": "研究主题（必填，从用户输入中提取的核心研究主题，用于后续 gap 分析。注意：topic 应该只是研究对象/领域，不要包含 gap 类型方向。例如用户输入「LLM的methodological gap」，topic 应填「Large Language Model」，gap_direction 填「Methodological Gap」）",
  "search_query": "检索关键词（必填，提取或生成最能代表用户研究意图的英文搜索词，不要包含 gap 类型词如「gap」）」",
  "gap_direction": "Gap 类型方向（可选，若用户明确指定了 gap 类型则填入，否则使用默认值空字符串 \"\" 表示分析所有类型。可识别的英文关键词包括：methodological/methodology/method → Methodological Gap，knowledge/theory/conceptual → Knowledge Gap，empirical/evidence/experimental → Evidence Gap，theoretical/theory/foundation → Theoretical Gap，population/people/user/group → Population Gap，contextual/temporal/time/context → Contextual/Time Gap。中文关键词同理）",
  "time_range": "年份范围（可选，格式如 \"2022-\" 或 \"2020-2026\"，若用户未指定则使用默认值 \"2020-\"）",
  "max_results": 最大检索数量（可选，整数，若用户未指定则使用默认值 50）
}}

直接输出纯 JSON，不要有其他内容。"""

        router_result = router_llm.call(router_prompt)
        task_storage.log("router", "ROUTER_RAW_OUTPUT", f"Raw router output:\n{router_result[:3000]}")

        # Parse router output to get correct params
        parsed = parse_router_output(router_result)
        if parsed:
            task_storage.log("router", "ROUTER_PARSED", f"Parsed params: {json.dumps(parsed, ensure_ascii=False)}")
            # Broadcast parsed params to frontend
            broadcast_event(task_storage.task_id, "router_params", parsed)
            # Override defaults with router-parsed values
            if parsed.get("topic"):
                default_inputs["topic"] = parsed["topic"]
            if parsed.get("search_query"):
                default_inputs["search_query"] = parsed["search_query"]
            if parsed.get("gap_direction") is not None:
                default_inputs["gap_direction"] = parsed["gap_direction"]
            if parsed.get("time_range"):
                default_inputs["time_range"] = parsed["time_range"]
            if parsed.get("max_results"):
                default_inputs["max_results"] = str(parsed["max_results"])
        else:
            task_storage.log("router", "ROUTER_WARN", f"Could not parse router output, using default inputs")

        # Fallback: detect gap_direction keywords in user input if still empty
        import re as _re
        user_lower = user_input.lower()
        gap_keyword_map = [
            ("Methodological Gap", ["methodological", "methodology gap", "方法论", "方法论空白"]),
            ("Knowledge Gap", ["knowledge gap", "知识空白", "知识 gap"]),
            ("Evidence Gap", ["empirical gap", "evidence gap", "证据空白", "实证空白"]),
            ("Theoretical Gap", ["theoretical gap", "theory gap", "理论空白"]),
            ("Population Gap", ["population gap", "人群空白", "用户空白"]),
            ("Contextual/Time Gap", ["contextual gap", "temporal gap", "time gap", "情境空白", "时间空白"]),
        ]
        for gap_type, keywords in gap_keyword_map:
            if any(kw in user_lower for kw in keywords):
                if not default_inputs.get("gap_direction"):
                    default_inputs["gap_direction"] = gap_type
                    task_storage.log("router", "ROUTER_FALLBACK", f"gap_direction fallback: detected '{gap_type}' from user input keywords")
                break

        task_storage.log("manager", "SYSTEM", f"Router parsed inputs: topic={default_inputs['topic']}, search_query={default_inputs['search_query']}, gap_direction={default_inputs['gap_direction']}, time_range={default_inputs['time_range']}, max_results={default_inputs['max_results']}")

        # Step 2: Create crew with correct inputs and run
        task_storage.log("manager", "SYSTEM", "Step 2: Running analysis crew with parsed parameters...")
        crew = create_research_gap_crew(task_storage, papers_dir, skip_router=True)
        result = crew.kickoff(inputs=default_inputs)

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
