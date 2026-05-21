"""Pydantic schemas for request/response models."""
from typing import Optional
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """POST /tasks request body."""
    query: str = Field(..., min_length=1, description="User's natural language research query")


class AgentLogEntry(BaseModel):
    agent: str
    status: str
    logs: list[str]


class TaskStatus(BaseModel):
    """GET /tasks/{task_id} response."""
    task_id: str
    task_name: str
    status: str  # "running" | "completed" | "failed"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    agent_logs: Optional[list[AgentLogEntry]] = None


class TaskCreateResponse(BaseModel):
    """POST /tasks response."""
    task_id: str
    status: str


class TaskListResponse(BaseModel):
    """GET /tasks response."""
    tasks: list[TaskStatus]
    total: int


class ReportResponse(BaseModel):
    """GET /reports/{task_id} response."""
    task_id: str
    report_content: str


class AgentLogResponse(BaseModel):
    """GET /reports/{task_id}/logs/{agent} response."""
    task_id: str
    agent: str
    log_content: str


class PaperInfo(BaseModel):
    """Paper metadata extracted from search results."""
    id: str
    title: str
    authors: list[str]
    year: Optional[int]
    abstract: Optional[str]
    citation_count: int
    url: str
    pdf_url: Optional[str]


class DataFileResponse(BaseModel):
    """GET /reports/{task_id}/data/{name} response."""
    task_id: str
    data_name: str
    content: dict
