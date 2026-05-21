# Research Gap Analysis Multi-Agent System

基于 CrewAI + arXiv API 构建的多智能体论文 gap 分析系统。

## 功能

- 输入自然语言研究需求，自动分解检索词
- 从 arXiv 检索相关论文
- 智能筛选相关性高的论文
- 按六类 gap（Knowledge/Methodological/Evidence/Population/Theoretical/Contextual）分析
- 支持指定 gap 方向分析，未指定则全部分析
- 每次运行独立存储，日志、论文、分析结果完全隔离

## 环境要求

- Python 3.10+
- DeepSeek API Key（用于子 Agent）
- Zhipu GLM API Key（用于 Manager Agent）

## 安装

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key
```

## 使用

```bash
# 分析特定 gap 方向
python -m src.main "帮我分析LLM在job recommendation领域methodological方向的gap"

# 分析所有 gap 方向
python -m src.main "帮我分析LLM在job recommendation领域的gap"

# 使用 CLI 入口
python src/cli.py "帮我分析LLM在job recommendation领域的gap"
```

## 架构

```
Manager Agent (glm-5.1)           # 总协调
├── Router Agent (deepseek-v4-pro)     # 分解查询
├── Searcher Agent (deepseek-v4-pro)   # 检索论文
├── Filter Agent (deepseek-v4-pro)     # 筛选相关性
├── Analyzer Agent (deepseek-v4-pro)  # 识别 gap
└── Synthesizer Agent (deepseek-v4-pro) # 生成报告
```

## 输出

每次运行的结果保存在 `outputs/{timestamp}_{topic_slug}/` 目录下：

- `logs/` - 各 Agent LLM 对话日志
- `papers/` - 下载的论文 PDF
- `data/` - JSON 格式的中间数据
- `report.md` - 最终 Markdown 报告
- `task_manifest.json` - 任务清单
