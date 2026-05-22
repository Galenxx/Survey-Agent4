# Research Gap Analysis

An AI-powered multi-agent system that automatically analyzes academic papers to identify research gaps. Built with [CrewAI](https://crewai.com/), DeepSeek, and Zhipu GLM.

[English](#english) | [中文](#中文)

---

## English

### Overview

Research Gap Analysis takes a natural-language research query and returns a structured Markdown report identifying underexplored areas in the literature. It uses a hierarchical multi-agent architecture:

1. **Parse** your query (topic, search terms, gap direction, time range)
2. **Search** Semantic Scholar + arXiv for relevant papers
3. **Filter** papers by relevance using LLM classification
4. **Analyze** each paper for six types of research gaps
5. **Synthesize** a final Markdown report

### Features

- **Natural language queries** — Ask in Chinese or English; no strict formatting required
- **Six gap types** — Knowledge, Methodological, Evidence, Population, Theoretical, Contextual/Time
- **Focus or full analysis** — Specify a gap direction (e.g., "methodological gap") or analyze all six
- **Isolated task storage** — Every run gets a timestamped directory with its own logs, papers, data, and report
- **Real-time streaming** — Watch agents work live via SSE in the web UI
- **Web app + CLI** — Use the browser UI or run from the command line

### Architecture

```
┌─────────────────────────────────────────────┐
│         Frontend  (React + Vite)            │
│     http://localhost:5173 (dev server)      │
└──────────────────┬──────────────────────────┘
                   │  HTTP + SSE
┌──────────────────▼──────────────────────────┐
│         Backend  (FastAPI + Uvicorn)        │
│          http://localhost:8000             │
└──────────────────┬──────────────────────────┘
                   │  CrewAI  (hierarchical)
┌──────────────────▼──────────────────────────┐
│          Core Engine  (src/)                │
│                                             │
│  Manager Agent (Zhipu GLM-5.1)             │
│   └──  Worker Agents (DeepSeek V4 Pro)        │
│        ├── Router    — Parse query          │
│        ├── Searcher  — Search papers         │
│        ├── Filter    — Classify relevance    │
│        ├── Analyzer  — Identify gaps (max reasoning) │
│        └── Synthesizer — Write report        │
└─────────────────────────────────────────────┘
```

### Six Gap Types

| Type | Chinese | What it identifies |
|------|---------|-------------------|
| **Knowledge Gap** | 知识空白 | Uncovered issues, concepts, or theoretical frameworks |
| **Methodological Gap** | 方法论空白 | Limitations of existing methods, missing techniques |
| **Evidence Gap** | 证据空白 | Lack of empirical validation, experiments, or large-scale data |
| **Population Gap** | 人群空白 | Limited research subjects, missing demographic groups |
| **Theoretical Gap** | 理论空白 | Missing conceptual models or theoretical foundations |
| **Contextual/Time Gap** | 情境/时间空白 | Outdated contexts or new environment considerations |

### Setup

**1. Install Python dependencies**

```bash
pip install -r requirements.txt
```

**2. Configure API keys**

```bash
cp .env.example .env
# Edit .env and add your keys:
#   DEEPSEEK_API_KEY=sk-...
#   ZHIPU_API_KEY=...
```

- **DeepSeek** — Used for all worker agents (Searcher, Filter, Analyzer, Synthesizer). Get a key at [platform.deepseek.com](https://platform.deepseek.com).
- **Zhipu GLM** — Used for the Manager Agent. Get a key at [bigmodel.cn](https://bigmodel.cn) (DashScope compatible API).

**3. Install frontend dependencies**

```bash
cd frontend && npm install && cd ..
```

### Usage

#### Web App (recommended)

Start both the backend and frontend with one command:

```bash
.\run_webapp.bat
```

Or start them individually:

```bash
# Terminal 1 — Backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Open http://localhost:5173 in your browser.

#### CLI

```bash
# Analyze a specific gap direction
python -m src.main "analyze methodological gaps in LLM-based job recommendation"

# Analyze all six gap types
python -m src.main "analyze LLM in job recommendation"

# Alternative CLI entry point
python src/cli.py "帮我分析LLM在job recommendation领域的gap"
```

### Output

Each run saves its output to `outputs/{timestamp}/`:

```
outputs/2026-05-22_120000/
├── task_manifest.json     # Task metadata and status
├── report.md              # Final Markdown report
├── logs/
│   ├── manager.log
│   ├── router.log
│   ├── searcher.log
│   ├── filter.log
│   ├── analyzer.log
│   └── synthesizer.log
├── papers/                # Downloaded PDFs
└── data/
    ├── search_results.json
    ├── filtered_papers.json
    └── gap_analysis.json
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Multi-Agent Framework | CrewAI 0.80+ |
| Worker LLM | DeepSeek V4 Pro (thinking: off; Analyzer: max reasoning) |
| Manager LLM | Zhipu GLM-5.1 (DashScope) |
| Paper Search | Semantic Scholar API + arXiv |
| PDF Processing | pdfplumber |
| Backend Framework | FastAPI 0.115+ |
| Backend Server | Uvicorn |
| Frontend | React 18 + TypeScript |
| Frontend Build | Vite 6 |
| Styling | Tailwind CSS 3 |

---

## 中文

### 概述

Research Gap Analysis 是一个 AI 驱动的多智能体系统，可自动分析学术论文并识别研究空白。输入自然语言研究问题，系统返回结构化的 Markdown 报告，帮助你快速了解某一领域的研究现状与空白。

系统核心流程：

1. **解析**你的查询（主题、检索词、gap 方向、时间范围）
2. **检索** Semantic Scholar + arXiv 相关论文
3. **筛选**通过 LLM 分类过滤高相关论文
4. **分析**按六类 gap 逐篇分析论文
5. **生成**最终 Markdown 报告

### 功能特性

- **自然语言输入** — 中文、英文均可，无需严格格式
- **六类 Gap 分析** — 知识空白、方法论空白、证据空白、人群空白、理论空白、情境/时间空白
- **聚焦或全量分析** — 可指定 gap 方向（如"方法论空白"），也可分析全部六类
- **任务隔离存储** — 每次运行独立目录，日志、论文、数据、报告完全隔离
- **实时流式输出** — Web 界面通过 SSE 实时观看 Agent 工作过程
- **Web 界面 + CLI 双入口** — 浏览器操作或命令行运行均可

### 系统架构

```
┌─────────────────────────────────────────────┐
│         前端  (React + Vite)                │
│     http://localhost:5173 (开发服务器)       │
└──────────────────┬──────────────────────────┘
                   │  HTTP + SSE
┌──────────────────▼──────────────────────────┐
│         后端  (FastAPI + Uvicorn)           │
│          http://localhost:8000              │
└──────────────────┬──────────────────────────┘
                   │  CrewAI (层级化流程)
┌──────────────────▼──────────────────────────┐
│          核心引擎  (src/)                   │
│                                             │
│  Manager Agent (Zhipu GLM-5.1)              │
│   └──  Worker Agents (DeepSeek V4 Pro)       │
│        ├── Router      — 解析查询            │
│        ├── Searcher    — 检索论文            │
│        ├── Filter      — 相关性分类           │
│        ├── Analyzer    — 识别 Gap (max深度思考) │
│        └── Synthesizer — 生成报告            │
└─────────────────────────────────────────────┘
```

### 六类 Gap

| 类型 | 中文 | 说明 |
|------|------|------|
| **Knowledge Gap** | 知识空白 | 未被探索的基础问题、概念或理论框架 |
| **Methodological Gap** | 方法论空白 | 现有方法的局限性、缺失的技术手段 |
| **Evidence Gap** | 证据空白 | 缺乏实证验证、实验或大规模数据 |
| **Population Gap** | 人群空白 | 研究对象局限，未覆盖特定群体 |
| **Theoretical Gap** | 理论空白 | 缺失理论框架或概念模型 |
| **Contextual/Time Gap** | 情境/时间空白 | 过时的研究情境或新环境考量 |

### 安装

**1. 安装 Python 依赖**

```bash
pip install -r requirements.txt
```

**2. 配置 API Key**

```bash
cp .env.example .env
# 编辑 .env，填入以下 Key：
#   DEEPSEEK_API_KEY=sk-...
#   ZHIPU_API_KEY=...
```

- **DeepSeek** — 用于所有 Worker Agent（Searcher、Filter、Analyzer、Synthesizer）。在 [platform.deepseek.com](https://platform.deepseek.com) 获取。
- **Zhipu GLM** — 用于 Manager Agent。在 [bigmodel.cn](https://bigmodel.cn) 获取（DashScope 兼容 API）。

**3. 安装前端依赖**

```bash
cd frontend && npm install && cd ..
```

### 使用方式

#### Web 界面（推荐）

一键启动后端和前端：

```bash
.\run_webapp.bat
```

或分别启动：

```bash
# 终端 1 — 后端
uvicorn backend.main:app --reload --port 8000

# 终端 2 — 前端
cd frontend && npm run dev
```

浏览器打开 http://localhost:5173。

#### 命令行

```bash
# 分析指定 gap 方向
python -m src.main "帮我分析LLM在job recommendation领域methodological方向的gap"

# 分析所有 gap 方向
python -m src.main "帮我分析LLM在job recommendation领域的gap"

# 也可使用 cli 入口
python src/cli.py "帮我分析LLM在job recommendation领域的gap"
```

### 输出目录结构

每次运行结果保存在 `outputs/{时间戳}/` 下：

```
outputs/2026-05-22_120000/
├── task_manifest.json     # 任务元信息与状态
├── report.md              # 最终 Markdown 报告
├── logs/
│   ├── manager.log        # Manager Agent 对话日志
│   ├── router.log
│   ├── searcher.log
│   ├── filter.log
│   ├── analyzer.log
│   └── synthesizer.log
├── papers/                # 下载的论文 PDF
└── data/
    ├── search_results.json   # 检索结果
    ├── filtered_papers.json  # 筛选后的论文
    └── gap_analysis.json      # Gap 分析结果
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 多智能体框架 | CrewAI 0.80+ |
| Worker LLM | DeepSeek V4 Pro（思考模式：关闭；Analyzer：max 深度思考） |
| Manager LLM | Zhipu GLM-5.1（DashScope） |
| 论文检索 | Semantic Scholar API + arXiv |
| PDF 处理 | pdfplumber |
| 后端框架 | FastAPI 0.115+ |
| 后端服务 | Uvicorn |
| 前端框架 | React 18 + TypeScript |
| 前端构建 | Vite 6 |
| 样式 | Tailwind CSS 3 |
