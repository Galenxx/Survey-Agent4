"""PDF 文本提取工具"""
import os
from typing import Optional
from crewai.tools import BaseTool
from pydantic import Field
import pdfplumber


class PdfToTextTool(BaseTool):
    """从 PDF 提取文本内容"""

    name: str = "pdf_to_text"
    description: str = "从 PDF 文件提取文本内容，用于后续分析"

    def _run(self, pdf_path: str, max_pages: int = 10) -> str:
        """
        提取 PDF 文本

        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大提取页数（用于长论文，控制 token 消耗）

        Returns:
            提取的文本内容
        """
        if not os.path.exists(pdf_path):
            return f"File not found: {pdf_path}"

        try:
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                num_pages = min(len(pdf.pages), max_pages)
                for i, page in enumerate(pdf.pages[:num_pages]):
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"[Page {i+1}]\n{text}")

            return "\n\n".join(text_parts) if text_parts else "No text extracted"

        except Exception as e:
            return f"Error extracting text: {str(e)}"
