"""Task management API routes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _parse_agent_log_content(content: str) -> list[str]:
    """Parse agent log content (single-line format: [timestamp] [category] content).

    Each line is one log entry in the format: [YYYY-MM-DD HH:MM:SS] [CATEGORY] message
    Returns the full content as a list of lines.
    """
    if not content:
        return []
    lines = content.strip().split("\n")
    return [line for line in lines if line.strip()]

from fastapi import APIRouter, HTTPException, Query

from backend.schemas.models import (
    AgentLogEntry,
    TaskCreate,
    TaskCreateResponse,
    TaskListResponse,
    TaskStatus,
)
from backend.services import task_reader
from backend.services.crew_executor import start_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreateResponse, status_code=201)
def create_task(body: TaskCreate) -> TaskCreateResponse:
    """Create and start a new research gap analysis task.

    The task runs asynchronously in the background. Poll GET /tasks/{task_id}
    to check its status.
    """
    from src.storage.task_storage import TaskStorage

    user_input = body.query.strip()

    # Check for duplicate running task:
    # - If manifest says "running" AND the process is alive -> return old task_id
    # - If manifest says "running" BUT process is dead (orphaned) -> proceed to create new task
    from backend.services.crew_executor import is_running
    all_tasks = task_reader.list_all_tasks()
    for t in all_tasks:
        if t.get("task_name") == user_input:
            tid = t.get("task_id", "")
            if t.get("status") == "running" and is_running(tid):
                return TaskCreateResponse(task_id=tid, status="running")
            # manifest says running but no process -> orphaned, fall through to create new task

    # Create TaskStorage for the new task
    task_storage = TaskStorage(task_name=user_input, base_dir="outputs")
    task_id = task_storage.task_id

    # Start background execution
    start_task(task_storage=task_storage)

    return TaskCreateResponse(task_id=task_id, status="running")


@router.get("", response_model=TaskListResponse)
def list_tasks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> TaskListResponse:
    """List all tasks, newest first."""
    all_tasks = task_reader.list_all_tasks()
    total = len(all_tasks)
    sliced = all_tasks[skip : skip + limit]
    tasks = [
        TaskStatus(
            task_id=t["task_id"],
            task_name=t["task_name"],
            status=t.get("status", "running"),
            start_time=t.get("start_time"),
            end_time=t.get("end_time"),
            summary=t.get("summary"),
            error=t.get("error"),
        )
        for t in sliced
    ]
    return TaskListResponse(tasks=tasks, total=total)


@router.get("/{task_id}", response_model=TaskStatus)
def get_task_status(task_id: str) -> TaskStatus:
    """Get the current status of a specific task."""
    try:
        manifest = task_reader.read_manifest(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    task_status = manifest.get("status", "running")
    final_status: str = "done" if task_status == "completed" else ("error" if task_status == "failed" else task_status)

    # Load agent logs from disk for completed/failed tasks
    agent_logs: list[AgentLogEntry] | None = None
    if task_status in ("completed", "failed"):
        agent_names = ["manager", "router", "searcher", "filter", "analyzer", "synthesizer"]
        all_logs = task_reader.read_all_agent_logs(task_id, agent_names)

        agent_logs = []
        for agent in agent_names:
            content = all_logs.get(agent, "")
            if content.strip():
                log_lines = _parse_agent_log_content(content)
                if log_lines:
                    agent_logs.append(AgentLogEntry(agent=agent, status=final_status, logs=log_lines))

    return TaskStatus(
        task_id=manifest["task_id"],
        task_name=manifest["task_name"],
        status=manifest.get("status", "running"),
        start_time=manifest.get("start_time"),
        end_time=manifest.get("end_time"),
        summary=manifest.get("summary"),
        error=manifest.get("error"),
        agent_logs=agent_logs if agent_logs else None,
    )


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str) -> None:
    """Delete a task and all its associated files."""
    if not task_reader.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    task_reader.delete_task(task_id)
