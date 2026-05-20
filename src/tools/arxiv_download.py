"""论文 PDF 下载工具"""
import hashlib
import os
import re
import time

import requests
from crewai.tools import BaseTool
from pydantic import Field


class PdfDownloadTool(BaseTool):
    """从任意 URL（arXiv、S2 等）下载论文 PDF"""

    name: str = "pdf_download"
    description: str = (
        "根据 PDF URL 下载论文 PDF 到指定目录。如果 URL 是 arXiv，会提取 arXiv ID 作为文件名。"
        "Args: pdf_url (str, required), paper_id (str, optional), output_dir (str, optional, 默认当前目录的 papers 子目录)。"
    )

    output_dir: str = Field(default="papers")

    def _run(
        self,
        pdf_url: str,
        paper_id: str | None = None,
        output_dir: str | None = None,
    ) -> str:
        output_dir = output_dir or self.output_dir or "papers"

        try:
            os.makedirs(output_dir, exist_ok=True)

            pdf_url = pdf_url.strip()
            if not pdf_url:
                return "Error: empty PDF URL"

            arxiv_id = self._extract_arxiv_id(pdf_url)
            if paper_id:
                safe_name = self._sanitize_filename(paper_id)
            elif arxiv_id:
                safe_name = self._sanitize_filename(arxiv_id)
            else:
                safe_name = hashlib.md5(pdf_url.encode()).hexdigest()[:16]

            output_path = os.path.abspath(os.path.join(output_dir, f"{safe_name}.pdf"))

            if os.path.exists(output_path):
                return output_path

            time.sleep(2)

            headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
            response = requests.get(
                pdf_url, headers=headers, timeout=60, allow_redirects=True
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and not response.content.startswith(
                b"%PDF"
            ):
                return f"Error: URL does not return a PDF (Content-Type: {content_type})"

            with open(output_path, "wb") as f:
                f.write(response.content)

            return output_path

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                return f"Error: Access forbidden (403) for {pdf_url}. Paper may be behind a paywall."
            return f"Error downloading: HTTP {e.response.status_code}"
        except requests.exceptions.Timeout:
            return f"Error: Download timeout for {pdf_url}"
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def _extract_arxiv_id(url: str) -> str:
        for pattern in [
            r"arxiv\.org/pdf/(\d+\.\d+)",
            r"arxiv\.org/abs/(\d+\.\d+)",
        ]:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        name = name.strip(". ")
        if len(name) > 200:
            name = name[:200]
        return name


ArxivDownloadTool = PdfDownloadTool
