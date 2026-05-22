"""Research Gap Crew - 研究 Gap 分析工作流

设计原则:
  - Manager Agent (GLM-5.1): 总协调，通过 CrewAI 的 manager_agent 机制真正参与决策
  - Router Agent (DeepSeek): 用户意图解析，生成结构化参数
  - Searcher/Filter/Analyzer/Synthesizer (DeepSeek): 实际执行搜索、筛选、分析、报告生成
"""
import json
import os
from crewai import Crew, Task, Agent, Process
from crewai.llms.providers.openai_compatible.completion import OpenAICompatibleCompletion
from typing import Dict, Any

from src.agents.manager_agent import create_manager_agent
from src.agents.router_agent import create_router_agent
from src.agents.searcher_agent import create_searcher_agent
from src.agents.filter_agent import create_filter_agent
from src.agents.analyzer_agent import create_analyzer_agent
from src.agents.synthesizer_agent import create_synthesizer_agent
from src.tools import (
    SemanticScholarSearchTool,
    ArxivSearchTool,
    PdfDownloadTool,
    PdfToTextTool,
    RelevanceClassifierTool,
    GapIdentifierTool,
    ReportWriterTool,
)
from src.storage.tool_wrapper import wrap_tool_for_logging
from src.storage.task_storage import TaskStorage
from backend.services.crew_executor import parse_router_output, broadcast_event


def _deepseek_llm(thinking: bool = False, reasoning_effort: str = "high"):
    """Create DeepSeek LLM instance (used by all Worker Agents).

    Args:
        thinking: Whether to enable thinking mode. Defaults to False.
        reasoning_effort: Reasoning effort when thinking mode is enabled.
            Use "max" for analyzer (deep analysis), "high" or "low" for others.
    """
    return OpenAICompatibleCompletion(
        model="deepseek-v4-pro",
        provider="deepseek",
        reasoning_effort=reasoning_effort,
        extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}},
        temperature=0,
    )


def _glm_llm(api_key: str = ""):
    """创建 GLM LLM 实例（供 Manager Agent 使用）"""
    import os as _os
    return OpenAICompatibleCompletion(
        model="glm-5.1",
        provider="dashscope",
        api_key=api_key or _os.getenv("GLM_API_KEY", ""),
        base_url="https://open.bigmodel.cn/api/paas/v4",
        temperature=0,
    )


def _wrap_tools(agent_key: str, task_storage: TaskStorage, papers_dir: str, tool_list):
    """为指定 agent 包装工具实例（带日志记录）"""
    def _inst(t_cls):
        if t_cls == PdfDownloadTool:
            return t_cls(output_dir=papers_dir)
        if t_cls == ArxivSearchTool:
            return t_cls(output_dir=papers_dir)
        return t_cls()
    return [wrap_tool_for_logging(_inst(t), agent_key=agent_key, task_storage=task_storage) for t in tool_list]


def create_research_gap_crew(
    task_storage: TaskStorage,
    papers_dir: str,
    parsed_params: Dict[str, Any],
    glm_api_key: str = "",
    skip_router: bool = False,
):
    """
    创建研究 Gap 分析 Crew。

    Args:
        task_storage: 任务存储实例（用于日志记录）
        papers_dir: 论文 PDF 下载目录
        parsed_params: Router 解析后的参数字典，包含:
            - topic: 研究主题
            - search_query: 检索关键词
            - gap_direction: Gap 类型方向（可选）
            - time_range: 年份范围
            - max_results: 最大检索数量
        glm_api_key: GLM API Key（留空则从环境变量读取）
        skip_router: 是否跳过 Router Agent（当 Router 结果已提前解析时设为 True）
    """
    papers_dir = os.path.abspath(papers_dir)
    topic = parsed_params.get("topic", "")
    search_query = parsed_params.get("search_query", "")
    gap_direction = parsed_params.get("gap_direction", "")
    time_range = parsed_params.get("time_range", "2020-")
    max_results = parsed_params.get("max_results", "50")

    task_storage.log("manager", "SYSTEM",
        f"Creating crew with: topic={topic}, search_query={search_query}, "
        f"gap_direction={gap_direction}, time_range={time_range}, max_results={max_results}")

    # Manager: GLM-5.1 做总协调
    manager_llm = _glm_llm(glm_api_key)
    manager = create_manager_agent(llm=manager_llm)

    # Workers: DeepSeek (thinking disabled by default; analyzer uses max reasoning)
    worker_llm = _deepseek_llm(thinking=False)
    analyzer_llm = _deepseek_llm(thinking=True, reasoning_effort="max")

    router_tools = _wrap_tools("router", task_storage, papers_dir, [])
    searcher_tools = _wrap_tools("searcher", task_storage, papers_dir,
        [SemanticScholarSearchTool, ArxivSearchTool, PdfDownloadTool])
    filter_tools = _wrap_tools("filter", task_storage, papers_dir,
        [RelevanceClassifierTool])
    analyzer_tools = _wrap_tools("analyzer", task_storage, papers_dir,
        [PdfToTextTool, GapIdentifierTool])
    synthesizer_tools = _wrap_tools("synthesizer", task_storage, papers_dir,
        [ReportWriterTool])

    router = create_router_agent(tools=router_tools, llm=worker_llm)
    searcher = create_searcher_agent(tools=searcher_tools, llm=worker_llm)
    filter_agent = create_filter_agent(tools=filter_tools, llm=worker_llm)
    analyzer = create_analyzer_agent(tools=analyzer_tools, llm=analyzer_llm)
    synthesizer = create_synthesizer_agent(tools=synthesizer_tools, llm=worker_llm)

    # Router Task: 仅在需要时创建
    if not skip_router:
        router_task = Task(
            description=f"""分析用户的研究需求，生成结构化的搜索查询参数。

请理解用户意图，从用户输入中提取或生成以下字段，输出为纯 JSON：
{{
  "topic": "研究主题（必填，从用户输入中提取的核心研究主题，用于后续 gap 分析）",
  "search_query": "检索关键词（必填，提取或生成最能代表用户研究意图的英文搜索词）",
  "gap_direction": "Gap 类型方向（可选，若用户明确指定了 gap 类型则填入，否则使用空字符串）",
  "time_range": "年份范围（可选，格式如 "2022-" 或 "2020-2026"）",
  "max_results": 最大检索数量（可选，整数）
}}

直接输出纯 JSON，不要有其他内容。""",
            agent=router,
            expected_output="结构化 JSON 格式的 SearchQuery",
        )

    # Searcher Task: 接收解析好的参数，直接执行
    searcher_task = Task(
        description=f"""根据以下参数检索并下载学术论文（使用两个数据源）。

检索关键词: {search_query}
年份范围: {time_range}
最大检索数量: {max_results}

请按以下步骤执行：

1. 使用 semantic_scholar_search 工具搜索 Semantic Scholar 论文数据库。
2. 使用 arxiv_search 工具搜索 arXiv 论文数据库。
3. 对两个数据源的搜索结果进行去重（按论文标题或 arXiv ID 精确匹配去重）。
4. 对去重后的论文，逐篇检查是否有 PDF 下载链接或本地路径：
   - 如果有 pdf_url，使用 pdf_download 工具下载 PDF。
   - 如果论文已有本地 PDF 文件（在 papers_dir 目录下），直接使用已有文件。
   - 如果没有 PDF 链接且无法下载，则标记该论文为"仅摘要"（不含 PDF）。
5. 将下载的论文 PDF 保存到目录: {papers_dir}

**输出格式要求**：
完成所有搜索和下载后，你必须返回一段**纯 JSON** 文本作为最终输出（不要有其他解释性文字）。JSON 结构如下：

{{
  "dedup_stats": {{
    "total_deduplicated": <去重后的论文总数>,
    "with_pdf": <有 PDF 的论文数>,
    "without_pdf": <无 PDF 的论文数>,
    "from_semantic_scholar": <来自 S2 的论文数>,
    "from_arxiv": <来自 arXiv 的论文数>
  }},
  "papers": [
    {{
      "id": "<论文 ID（首选 arXiv ID）>",
      "arxiv_id": "<arXiv ID（如有）>",
      "title": "<论文标题>",
      "authors": "<所有作者，格式：First Last, First Last, ...>",
      "year": "<发表年份>",
      "abstract": "<摘要>",
      "citation_count": <引用数>,
      "pdf_path": "<本地 PDF 路径（如有）>",
      "pdf_url": "<PDF 下载链接（如有）>",
      "source": "<semantic_scholar 或 arxiv>"
    }}
  ]
}}

**关键要求**：
- **必须对所有19篇论文都输出**，包括有 PDF 和没有 PDF 的
- authors 字段必须是字符串，格式："Name1, Name2, Name3"
- year 字段必须是字符串或数字，不能为空
- 所有论文都必须列出，不能遗漏任何一篇""",
        agent=searcher,
        expected_output="纯 JSON 格式的论文列表（无其他文字），包含所有去重后论文的元数据（ID、标题、作者、年份、摘要、PDF路径、来源）和去重统计",
    )

    # Filter Task: 接收解析好的参数，直接执行
    filter_task = Task(
        description=f"""评估论文与研究主题的相关性，筛选高质量的相关论文。

研究主题: {topic}
Gap 分析重点: {gap_direction if gap_direction else '全部类型（分析所有六类 gap）'}

1. 对搜索结果中的每篇论文，使用 classify_relevance 工具判断相关性
2. 筛选出与研究主题相关的论文（至少10篇）
3. 返回相关论文列表

请使用 classify_relevance 工具逐篇评估论文相关性。""",
        agent=filter_agent,
        expected_output="筛选后的相关论文列表",
        context=[searcher_task] if skip_router else [searcher_task],
    )

    # Analyzer Task: 接收解析好的参数，直接执行
    gap_focus_note = (
        f"本次分析只识别 **{gap_direction}**，无需分析其他 gap 类型。"
        if gap_direction else
        "本次分析识别全部六类 gap: Methodological Gap、Knowledge Gap、Evidence Gap、Theoretical Gap、Population Gap、Contextual/Time Gap。"
    )
    analyzer_task = Task(
        description=f"""分析论文中的研究 gap。

研究主题: {topic}
{gap_focus_note}

对于筛选出的相关论文：
1. 使用 pdf_to_text 工具提取论文文本（前10页），PDF 文件在 {papers_dir} 目录下。
2. 使用 identify_gap 工具识别 gap，**必须传入以下参数**：
   - paper_title: 论文标题（从论文搜索结果中获取）
   - paper_authors: 论文作者（从论文搜索结果中获取，格式如 "Nils Beutling, Maja Spahic-Bogdanovic"）
   - paper_year: 论文年份（从论文搜索结果中获取）
   - paper_text: 提取的 PDF 文本
   - gap_direction: "{gap_direction}"
3. 返回每篇论文的 gap 分析结果（JSON 格式），包含 paper_title、paper_authors、paper_year 和 gaps 字段。

重要约束：
- **只分析有本地 PDF 文件的论文**。如果某篇论文没有 PDF 文件（在 {papers_dir} 目录下找不到对应的 .pdf 文件），则该论文应标记为"跳过：无PDF文件"，不要尝试猜测文件名或基于标题/摘要编造分析结果。
- **禁止编造 gap 分析**。如果无法从 PDF 提取论文正文，必须如实说明论文无法分析（跳过），绝不能基于论文标题或摘要推断 gap 内容。
- **必须传入 authors 和 year**：identify_gap 工具已支持 paper_authors 和 paper_year 参数，调用时必须填入从搜索结果中获取的元数据。
- 如果所有相关论文都没有 PDF 文件，则应返回明确的失败状态，并说明原因：所有论文的 PDF 均无法获取，无法进行 gap 分析。
- 只有成功提取了 PDF 文本的论文才能进入 gap 分析环节。

请使用 pdf_to_text 和 identify_gap 工具分析每篇论文的 gap，确保每条分析结果都包含 paper_title、paper_authors、paper_year 和 gaps 字段。""",
        agent=analyzer,
        expected_output="论文 gap 分析结果列表（JSON 格式），每条结果必须包含：paper_title、paper_authors、paper_year、gaps，以及被跳过的论文（无 PDF）列表",
        context=[filter_task],
    )

    # Synthesizer Task: 接收解析好的参数，直接执行
    synthesizer_task = Task(
        description=f"""汇总所有 gap 分析结果，生成结构化的 Markdown 研究报告。

研究主题: {topic}
Gap 分析重点: {gap_direction if gap_direction else '全部六类 gap'}

请严格按照以下结构生成报告，不要偏离格式：

# 研究 Gap 分析报告

（自动生成，包含生成时间）

## 1. 报告元信息

使用 Markdown 表格，包含：研究主题、Gap 分析方向、分析日期、总相关论文数、已分析论文数、无 PDF 跳过论文数等。

## 2. 研究概述

2-3段文字描述分析背景和总体发现。

## 3. Gap 分析结果总览

### 3.1 总体统计

使用无序列表，包含：已分析论文数、无 PDF 跳过的论文数、存在 gap 的论文数、识别的关键 Gap 主题数。

### 3.2 Gap 主题分布概览

使用 Markdown 表格，列：序号、Gap 主题、涉及论文数、涉及论文。

## 4. 按 Gap 主题分类的详细分析

对每个 Gap 主题，使用以下结构：

### 主题X：主题名称

**核心问题**：一句话描述核心问题。

---

#### 论文标题（去掉编号和emoji）

- **作者**：必须使用 analyze 环节传入的 paper_authors 字段值，不要留空或自行推断。
- **年份**：必须使用 analyze 环节传入的 paper_year 字段值，不要留空或自行推断。
- **Gap 描述**：

  （Gap 描述的详细文本，使用缩进）

注意：
- 论文标题是 H4，前面不要有列表符号
- **作者和年份必须直接使用传入数据**，即使为空也如实写"未提供"，不要自行推断
- Gap 描述是同一级别的列表项（都用 `-` 开头）
- Gap 描述后面跟缩进的正文，不要嵌套额外的列表
- 不要重复任何内容
- 不要在标题里加粗或使用特殊符号（只用纯文本标题）

## 5. 未分析论文说明（如有）

列出所有因缺少 PDF 而被跳过的论文，包括论文标题和跳过原因。
如果所有论文都被成功分析，则本节填写"无"。

## 6. 研究发现总结与未来方向建议

## 附录：论文索引

---

报告路径: {task_storage.get_report_path()}

请使用 write_report 工具将分析结果写入报告文件。""",
        agent=synthesizer,
        expected_output="Markdown 格式的研究报告（已写入文件），包含成功分析的论文 gap 结果和被跳过论文的说明",
        context=[analyzer_task],
    )

    # 组装 agents 和 tasks（Manager 不放入 agents 列表，由 manager_agent 单独指定）
    # 注意：hierarchical 模式下 manager 只能通过 manager_agent 指定，不能放在 agents 列表中
    worker_agents = [searcher, filter_agent, analyzer, synthesizer]
    tasks = [searcher_task, filter_task, analyzer_task, synthesizer_task]
    if not skip_router:
        worker_agents.insert(0, router)
        tasks.insert(0, router_task)

    crew = Crew(
        agents=worker_agents,
        tasks=tasks,
        manager_agent=manager,
        process=Process.hierarchical,
        verbose=True,
    )

    return crew


def run_research_gap_analysis(
    user_input: str,
    task_storage: TaskStorage,
    use_glm_for_router: bool = False,
) -> Dict[str, Any]:
    """
    运行研究 Gap 分析。

    Args:
        user_input: 用户输入的自然语言研究需求
        task_storage: 任务存储实例
        use_glm_for_router: 是否用 GLM-5.1 做 Router 解析（默认 False，用 DeepSeek）

    Returns:
        执行结果字典
    """
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        import os as _os

        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(env_path)
        glm_api_key = _os.getenv("GLM_API_KEY", "")

        papers_dir = os.path.abspath(task_storage.get_papers_dir())
        task_storage.log("manager", "SYSTEM", f"Starting analysis for: {user_input}")

        # ── Step 1: Router ──────────────────────────────────────────
        # Router 走直接 LLM 调用（不通过 crew），更可靠
        task_storage.log("manager", "SYSTEM", "Step 1: Running Router Agent to parse user input...")

        router_llm = _glm_llm(glm_api_key) if use_glm_for_router else _deepseek_llm(thinking=False)
        router_provider = "GLM-5.1" if use_glm_for_router else "DeepSeek"
        task_storage.log("manager", "SYSTEM", f"Router using: {router_provider}")

        router_prompt = f"""分析用户的研究需求，生成结构化的搜索查询参数。

用户输入: {user_input}

请理解用户意图，从用户输入中提取或生成以下字段，输出为纯 JSON：
{{
  "topic": "研究主题（必填，从用户输入中提取的核心研究主题，用于后续 gap 分析。注意：topic 应该只是研究对象/领域，不要包含 gap 类型方向。例如用户输入「LLM的methodological gap」，topic 应填「Large Language Model」，gap_direction 填「Methodological Gap」）",
  "search_query": "检索关键词（必填，基于 topic 生成最能代表用户研究意图的英文搜索词，不要包含任何 gap 类型相关词汇，如 gap、methodology、methodological、knowledge、evidence、theoretical、population、contextual、temporal 等，不要添加 gap 类型方向信息）",
  "gap_direction": "Gap 类型方向（可选，若用户明确指定了 gap 类型则填入，否则使用空字符串。可识别的英文关键词包括：methodological/methodology/method → Methodological Gap，knowledge/theory/conceptual → Knowledge Gap，empirical/evidence/experimental → Evidence Gap，theoretical/theory/foundation → Theoretical Gap，population/people/user/group → Population Gap，contextual/temporal/time/context → Contextual/Time Gap。中文关键词同理）",
  "time_range": "年份范围（可选，格式如 "2022-" 或 "2020-2026"，若用户未指定则使用默认值 "2020-"）",
  "max_results": 最大检索数量（可选，整数，若用户未指定则使用默认值 50）
}}

直接输出纯 JSON，不要有其他内容。"""

        router_result = router_llm.call(router_prompt)
        task_storage.log("router", "ROUTER_RAW_OUTPUT", f"Raw router output:\n{router_result[:3000]}")

        # ── Step 2: 解析 Router 输出 ─────────────────────────────────
        parsed = parse_router_output(router_result)
        if parsed:
            task_storage.log("router", "ROUTER_PARSED", f"Parsed params: {json.dumps(parsed, ensure_ascii=False)}")
            broadcast_event(task_storage.task_id, "router_params", parsed)
        else:
            task_storage.log("router", "ROUTER_WARN", f"Could not parse router output, using defaults")
            parsed = {}

        # 默认值兜底
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
        for k, v in parsed.items():
            if v is not None and v != "":
                default_inputs[k] = v
        # search_query 直接使用 topic，不再单独生成
        if default_inputs.get("topic"):
            default_inputs["search_query"] = default_inputs["topic"]
        # max_results 转字符串（crew kickoff 需要）
        if isinstance(default_inputs.get("max_results"), (int, float)):
            default_inputs["max_results"] = str(int(default_inputs["max_results"]))

        # ── Step 3: Fallback 检测 gap_direction ────────────────────
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
                    task_storage.log("router", "ROUTER_FALLBACK",
                        f"gap_direction fallback: detected '{gap_type}' from user input keywords")
                break

        task_storage.log("manager", "SYSTEM",
            f"Router parsed: topic={default_inputs['topic']}, "
            f"search_query={default_inputs['search_query']}, "
            f"gap_direction={default_inputs['gap_direction']}, "
            f"time_range={default_inputs['time_range']}, "
            f"max_results={default_inputs['max_results']}")

        # ── Step 4: 创建并运行 Crew（Manager=GLM-5.1, Workers=DeepSeek）──
        task_storage.log("manager", "SYSTEM",
            "Step 2: Running Crew (Manager=GLM-5.1, Workers=DeepSeek)...")
        crew = create_research_gap_crew(
            task_storage=task_storage,
            papers_dir=papers_dir,
            parsed_params=default_inputs,
            glm_api_key=glm_api_key,
            skip_router=True,  # Router 已提前完成
        )
        result = crew.kickoff(inputs={})

        task_storage.log("manager", "SYSTEM", "Analysis workflow completed successfully.")
        task_storage.complete(summary=str(result)[:500])

        return {
            "status": "success",
            "result": str(result),
            "task_id": task_storage.task_id,
            "report_path": task_storage.get_report_path(),
        }

    except Exception as e:
        import traceback
        task_storage.log("manager", "ERROR",
            f"Analysis failed: {str(e)}\n{traceback.format_exc()}")
        task_storage.fail(str(e))
        return {
            "status": "failed",
            "error": str(e),
            "task_id": task_storage.task_id,
        }
