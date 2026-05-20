"""报告写入工具"""
import os
from datetime import datetime
from crewai.tools import BaseTool


class ReportWriterTool(BaseTool):
    """将分析结果追加写入 Markdown 报告"""

    name: str = "write_report"
    description: str = "将分析结果追加写入 Markdown 格式的报告文件"

    def _run(self, content: str, output_path: str, append: bool = True) -> str:
        """
        写入报告

        Args:
            content: 报告内容（Markdown 格式）
            output_path: 输出文件路径
            append: 是否追加模式（默认 True）

        Returns:
            写入状态和文件路径
        """
        try:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

            mode = "a" if append and os.path.exists(output_path) else "w"

            with open(output_path, mode, encoding="utf-8") as f:
                if mode == "w":
                    f.write(f"# 研究 Gap 分析报告\n\n")
                    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
                f.write(content)
                f.write("\n\n")

            return f"Report written to {output_path}"

        except Exception as e:
            return f"Error writing report: {str(e)}"
