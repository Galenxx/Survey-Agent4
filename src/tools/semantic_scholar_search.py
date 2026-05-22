"""Semantic Scholar 搜索工具（搜索后自动下载 PDF）"""
import json
import os
import re
import time
import requests
from crewai.tools import BaseTool
from pydantic import Field


def _rate_limited_request(url: str, params: dict, headers: dict, timeout: int = 30) -> requests.Response:
    """发送 HTTP 请求，自动处理 Rate Limit（指数退避重试）"""
    max_retries = 5
    base_delay = 2
    for attempt in range(max_retries):
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", base_delay * (2 ** attempt)))
            time.sleep(retry_after)
            continue
        return response
    return response


def _download_pdf(url: str, paper_id: str, output_dir: str) -> str:
    """下载 PDF 文件，返回本地路径或错误信息"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", paper_id)
        safe_name = safe_name.strip(". ")
        if len(safe_name) > 200:
            safe_name = safe_name[:200]
        output_path = os.path.abspath(os.path.join(output_dir, f"{safe_name}.pdf"))
        if os.path.exists(output_path):
            return output_path
        time.sleep(1.5)
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}, timeout=60, allow_redirects=True)
        if response.status_code == 403:
            return f"Error: Access forbidden (403)"
        if response.status_code == 404:
            return f"Error: PDF not found (404)"
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
            return f"Error: Not a PDF (Content-Type: {content_type})"
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path
    except requests.exceptions.Timeout:
        return f"Error: Download timeout"
    except requests.exceptions.HTTPError as e:
        return f"Error: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


class SemanticScholarSearchTool(BaseTool):
    """搜索 Semantic Scholar 论文数据库，只返回有可下载 PDF 的论文，并自动下载 PDF"""

    name: str = "semantic_scholar_search"
    description: str = (
        "搜索 Semantic Scholar 论文数据库，只返回有可下载 PDF 的论文，并自动下载 PDF。 "
        "返回论文 ID、标题、摘要、作者、年份、引用量、PDF 下载链接、PDF 本地路径和 arXiv ID（如适用）。"
    )
    output_dir: str = Field(default="papers")

    def _run(self, query: str, max_results: int = 50, year_range: str = "") -> str:
        """
        执行 Semantic Scholar 搜索（仅返回有 PDF 的论文），并自动下载 PDF

        Args:
            query: 搜索查询词
            max_results: 最大返回结果数（默认50）
            year_range: 年份范围，格式如 "2022-2026" 或 "2022-" 或 "-2026"

        Returns:
            JSON 格式的论文列表（含 PDF 本地路径和 arXiv ID）
        """
        output_dir = self.output_dir or "papers"
        try:
            os.makedirs(output_dir, exist_ok=True)
            api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
            headers = {"x-api-key": api_key} if api_key else {}
            base_url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"

            all_papers = []
            token = None
            retrieved = 0

            while retrieved < max_results:
                params = {
                    "query": query,
                    "fields": "paperId,title,authors,abstract,year,citationCount,url,openAccessPdf",
                    "sort": "citationCount",
                    "openAccessPdf": "true",
                }

                if year_range:
                    if "-" in year_range:
                        parts = year_range.split("-")
                        if parts[0]:
                            params["year"] = f"{parts[0]}-"
                        elif parts[1]:
                            params["year"] = f"-{parts[1]}"
                    else:
                        params["year"] = year_range

                if token:
                    params["token"] = token

                response = _rate_limited_request(base_url, params=params, headers=headers, timeout=30)

                if response.status_code == 401:
                    return "Semantic Scholar API authentication failed. Check your API key."

                if response.status_code == 429:
                    return "Semantic Scholar API is heavily rate limited. Please try again later."

                if response.status_code != 200:
                    return f"Semantic Scholar API error: {response.status_code}"

                data = response.json()
                papers = data.get("data", [])
                total = data.get("total", 0)

                if not papers:
                    break

                for paper in papers:
                    if retrieved >= max_results:
                        break

                    oap = paper.get("openAccessPdf") or {}
                    pdf_url = oap.get("url", "")

                    if not pdf_url:
                        continue

                    paper_id = paper.get("paperId", "")
                    arxiv_id = self._extract_arxiv_id(pdf_url) or ""

                    # 自动下载 PDF
                    pdf_path = _download_pdf(pdf_url, arxiv_id or paper_id, output_dir)

                    paper_info = {
                        "id": paper_id,
                        "arxiv_id": arxiv_id,
                        "title": paper.get("title", ""),
                        "authors": [
                            {"name": a.get("name", ""), "authorId": a.get("authorId", "")}
                            for a in paper.get("authors", [])
                        ],
                        "abstract": paper.get("abstract", ""),
                        "year": paper.get("year"),
                        "citationCount": paper.get("citationCount", 0),
                        "url": paper.get("url", ""),
                        "pdf_url": pdf_url,
                        "pdf_path": pdf_path,
                        "pdf_status": oap.get("status", ""),
                    }
                    all_papers.append(paper_info)
                    retrieved += 1

                if not data.get("token"):
                    break
                token = data["token"]

                if papers:
                    time.sleep(1.1)

            result = {
                "source": "semantic_scholar",
                "total": total,
                "retrieved": len(all_papers),
                "papers": all_papers,
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def _extract_arxiv_id(pdf_url: str) -> str:
        """从 PDF URL 中提取 arXiv ID"""
        patterns = [
            r"arxiv\.org/pdf/(\d+\.\d+)",
            r"arxiv\.org/abs/(\d+\.\d+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, pdf_url)
            if m:
                return m.group(1)
        return ""
