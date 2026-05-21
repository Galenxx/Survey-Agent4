"""Report and data API routes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from backend.schemas.models import ReportResponse, AgentLogResponse
from backend.services import task_reader

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{task_id}")
def get_report(task_id: str) -> ReportResponse:
    """Get the raw markdown report for a completed task."""
    if not task_reader.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    try:
        content = task_reader.read_report(task_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Report not yet available for task: {task_id}. "
            "The task may still be running or failed.",
        )

    return ReportResponse(task_id=task_id, report_content=content)


@router.get("/{task_id}/download")
def download_report(task_id: str) -> PlainTextResponse:
    """Download the report as a plain text/markdown file."""
    if not task_reader.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    try:
        content = task_reader.read_report(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report not found")

    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{task_id}_report.md"'},
    )


@router.get("/{task_id}/logs/{agent}")
def get_agent_log(task_id: str, agent: str) -> AgentLogResponse:
    """Get the log output for a specific agent."""
    if not task_reader.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    log_content = task_reader.read_agent_log(task_id, agent)
    return AgentLogResponse(task_id=task_id, agent=agent, log_content=log_content)


@router.get("/{task_id}/data/{name}")
def get_data_file(task_id: str, name: str):
    """Get a specific intermediate data file (search_results, filtered_papers, gap_analysis)."""
    if not task_reader.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    try:
        data = task_reader.get_data_file(task_id, name)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Data file '{name}' not found for task: {task_id}",
        )

    return data


@router.get("/{task_id}/papers")
def get_papers(task_id: str):
    """Get the papers list from search results."""
    if not task_reader.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    papers = task_reader.get_papers(task_id)
    return {"task_id": task_id, "data_files": papers}
