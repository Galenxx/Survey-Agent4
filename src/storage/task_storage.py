"""任务隔离存储模块"""
import os
import json
from datetime import datetime


class TaskStorage:
    """每次运行的任务隔离存储"""

    def __init__(self, task_name: str, base_dir: str = "outputs"):
        self.task_name = task_name
        self.base_dir = base_dir
        self.start_time = datetime.now()
        self.task_id = self.start_time.strftime("%Y-%m-%d_%H%M%S")
        self.task_dir = os.path.join(base_dir, self.task_id)

        self.logs_dir = os.path.join(self.task_dir, "logs")
        self.papers_dir = os.path.join(self.task_dir, "papers")
        self.data_dir = os.path.join(self.task_dir, "data")

        self._ensure_dirs()

        self.manifest = {
            "task_id": self.task_id,
            "task_name": task_name,
            "start_time": datetime.now().isoformat(),
            "status": "running",
        }
        self._save_manifest()

    def _ensure_dirs(self):
        """创建必要的目录结构"""
        for dir_path in [self.logs_dir, self.papers_dir, self.data_dir]:
            os.makedirs(dir_path, exist_ok=True)

    def _save_manifest(self):
        """保存任务清单"""
        manifest_path = os.path.join(self.task_dir, "task_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=2)

    def get_agent_log_path(self, agent_name: str) -> str:
        """获取指定 Agent 的日志文件路径"""
        return os.path.join(self.logs_dir, f"{agent_name}.log")

    def read_agent_log(self, agent_name: str) -> str:
        """读取指定 Agent 的完整日志内容"""
        log_path = self.get_agent_log_path(agent_name)
        if not os.path.exists(log_path):
            return ""
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def log(self, agent_name: str, category: str, content: str):
        """保存 Agent 日志（单行格式：[时间] [类别] 内容）"""
        log_path = self.get_agent_log_path(agent_name)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"[{timestamp}] [{category}] {content}\n")

    def save_data(self, filename: str, data: dict):
        """保存 JSON 数据"""
        data_path = os.path.join(self.data_dir, filename)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data_path

    def save_search_results(self, data: dict):
        """保存搜索结果"""
        return self.save_data("search_results.json", data)

    def save_filtered_papers(self, data: dict):
        """保存筛选后的论文"""
        return self.save_data("filtered_papers.json", data)

    def save_gap_analysis(self, data: dict):
        """保存 Gap 分析结果"""
        return self.save_data("gap_analysis.json", data)

    def get_papers_dir(self) -> str:
        """获取论文目录路径"""
        return self.papers_dir

    def get_report_path(self) -> str:
        """获取报告文件路径"""
        return os.path.join(self.task_dir, "report.md")

    def complete(self, summary: str = ""):
        """标记任务完成"""
        self.manifest["status"] = "completed"
        self.manifest["end_time"] = datetime.now().isoformat()
        self.manifest["summary"] = summary
        self._save_manifest()

    def fail(self, error: str):
        """标记任务失败"""
        self.manifest["status"] = "failed"
        self.manifest["end_time"] = datetime.now().isoformat()
        self.manifest["error"] = error
        self._save_manifest()
