"""arXiv 搜索工具"""
import json
import os
import re
import time
import hashlib
from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import Field


def _rate_limited_request(url: str, params: dict, headers: dict, timeout: int = 30) -> requests.Response:
    """发送 HTTP 请求，自动处理 Rate Limit（指数退避重试）"""
    max_retries = 5
    base_delay = 5
    for attempt in range(max_retries):
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", base_delay * (2 ** attempt)))
            time.sleep(retry_after)
            continue
        return response
    return response


class ArxivSearchTool(BaseTool):
    """搜索 arXiv 论文数据库，下载 PDF 并返回元数据"""

    name: str = "arxiv_search"
    description: str = (
        "搜索 arXiv 论文数据库，根据查询词检索相关论文并下载 PDF。"
        "Args: query (str, required), max_results (int, default 30), year_range (str, optional)."
    )

    output_dir: str = Field(default="papers")

    def _run(
        self,
        query: str,
        max_results: int = 30,
        year_range: str = "",
    ) -> str:
        """
        搜索 arXiv 并下载 PDF

        Args:
            query: 搜索查询词
            max_results: 最大返回结果数（默认30）
            year_range: 年份范围，格式如 "2022-" 或 "2020-2026"（可选）

        Returns:
            JSON 格式的论文列表（含 PDF 路径和 arXiv ID）
        """
        output_dir = self.output_dir or "papers"
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception:
            pass

        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}

            search_query = self._build_query(query, year_range)
            params = {
                "search_query": search_query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }

            base_url = "http://export.arxiv.org/api/query"
            response = _rate_limited_request(base_url, params=params, headers=headers, timeout=60)

            if response.status_code == 429:
                return "arXiv API is heavily rate limited. Please try again later."

            if response.status_code != 200:
                return f"arXiv API error: {response.status_code}"

            papers = self._parse_atom_feed(response.text, output_dir)

            result = {
                "source": "arxiv",
                "total": len(papers),
                "retrieved": len(papers),
                "papers": papers,
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: {str(e)}"

    def _build_query(self, query: str, year_range: str) -> str:
        """构建 arXiv 查询语句"""
        conditions = [f"all:{query}"]
        if year_range:
            if "-" in year_range:
                parts = year_range.split("-")
                if parts[0]:
                    conditions.append(f" submittedDate:[{parts[0]} TO *]")
                elif parts[1]:
                    conditions.append(f" submittedDate:[* TO {parts[1]}]")
        return " AND ".join(conditions)

    def _parse_atom_feed(self, xml_text: str, output_dir: str) -> list:
        """解析 arXiv Atom Feed，提取论文元数据并下载 PDF"""
        papers = []

        entry_pattern = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)
        for entry_match in entry_pattern.finditer(xml_text):
            entry = entry_match.group(1)

            def extract(tag):
                m = re.search(f"<{tag}>(.*?)</{tag}>", entry, re.DOTALL)
                return m.group(1).strip() if m else ""

            title = re.sub(r"\s+", " ", extract("title"))
            abstract = re.sub(r"\s+", " ", extract("summary"))
            paper_id = extract("id").split("/")[-1]
            published = extract("published")
            year = ""
            if published:
                year = published[:4]
            authors = [
                {"name": re.sub(r"\s+", " ", n.strip())}
                for n in re.findall(r"<name>(.*?)</name>", entry)
            ]
            pdf_url = ""
            for link in re.finditer(r'<link[^>]+>', entry):
                link_str = link.group(0)
                if 'title="pdf"' in link_str or 'type="application/pdf"' in link_str:
                    m = re.search(r'href="(.*?)"', link_str)
                    if m:
                        pdf_url = m.group(1)
                        break
            if not pdf_url:
                m = re.search(r'<link[^>]+href="(.*?\.pdf)"[^>]*>', entry)
                if m:
                    pdf_url = m.group(1)
            if not pdf_url:
                arxiv_id = paper_id
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            pdf_path = self._download_pdf(pdf_url, paper_id, output_dir)

            papers.append({
                "id": paper_id,
                "arxiv_id": paper_id,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "year": year,
                "citationCount": 0,
                "url": f"https://arxiv.org/abs/{paper_id}",
                "pdf_url": pdf_url,
                "pdf_path": pdf_path,
            })

        return papers

    def _download_pdf(self, pdf_url: str, paper_id: str, output_dir: str) -> str:
        """下载 PDF 文件"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            safe_name = self._sanitize_filename(paper_id)
            output_path = os.path.abspath(os.path.join(output_dir, f"{safe_name}.pdf"))

            if os.path.exists(output_path):
                return output_path

            time.sleep(3)

            response = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60, allow_redirects=True)
            if response.status_code == 403:
                return f"Error: Access forbidden (403) for {pdf_url}"
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
                return f"Error: URL does not return a PDF (Content-Type: {content_type})"

            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path

        except requests.exceptions.Timeout:
            return f"Error: Download timeout for {pdf_url}"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                return f"Error: Access forbidden (403) for {pdf_url}"
            return f"Error downloading: HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        name = name.strip(". ")
        if len(name) > 200:
            name = name[:200]
        return name
