"""Test fixtures and configuration"""
import pytest
import os
import tempfile
import shutil
from src.storage.task_storage import TaskStorage


@pytest.fixture
def temp_output_dir():
    """创建临时输出目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def task_storage(temp_output_dir):
    """创建任务存储实例"""
    return TaskStorage(task_name="test_task", base_dir=temp_output_dir)


@pytest.fixture
def sample_search_query():
    """示例搜索查询"""
    return {
        "topic": "LLM in job recommendation",
        "direction": "methodological",
        "gap_direction": "Methodological Gap",
        "time_range": "2022-2026",
        "max_results": 50,
    }


@pytest.fixture
def sample_paper():
    """示例论文"""
    return {
        "id": "2301.12345",
        "title": "Large Language Models for Job Recommendation: A Survey",
        "authors": ["Author One", "Author Two"],
        "abstract": "This paper surveys the application of LLMs in job recommendation...",
        "published": "2024-01-15",
        "categories": ["cs.IR", "cs.CL"],
        "pdf_url": "https://arxiv.org/pdf/2301.12345.pdf",
    }


@pytest.fixture
def sample_gap_analysis():
    """示例 Gap 分析结果"""
    return {
        "paper_id": "2301.12345",
        "title": "Large Language Models for Job Recommendation: A Survey",
        "gaps": {
            "Knowledge Gap": {
                "exists": True,
                "description": "缺乏对新兴多模态 LLM 在招聘场景应用的系统研究"
            },
            "Methodological Gap": {
                "exists": True,
                "description": "现有方法未充分考虑职位描述的动态更新和实时性"
            },
            "Evidence Gap": {
                "exists": False,
                "description": "已有大量实证研究验证"
            },
            "Population Gap": {
                "exists": True,
                "description": "研究主要集中于英语市场，缺少对其他语言的覆盖"
            },
            "Theoretical Gap": {
                "exists": False,
                "description": "理论基础较为完善"
            },
            "Contextual/Time Gap": {
                "exists": True,
                "description": "多数研究基于 GPT-3 时代的数据，未考虑 ChatGPT 后的影响"
            },
        }
    }
