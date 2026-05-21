"""Service for reading task state from the existing TaskStorage file structure."""
import json
import os
from pathlib import Path
from typing import Optional
from backend.config import OUTPUTS_DIR


def _task_dir(task_id: str) -> Path:
    return OUTPUTS_DIR / task_id


def _manifest_path(task_id: str) -> Path:
    return _task_dir(task_id) / "task_manifest.json"


def read_manifest(task_id: str) -> dict:
    """Read task_manifest.json for a given task_id."""
    path = _manifest_path(task_id)
    if not path.exists():
        raise FileNotFoundError(f"Task manifest not found: {task_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_report(task_id: str) -> str:
    """Read the final report.md for a given task_id."""
    path = _task_dir(task_id) / "report.md"
    if not path.exists():
        raise FileNotFoundError(f"Report not found for task: {task_id}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_agent_log(task_id: str, agent: str) -> str:
    """Read an agent log file for a given task_id and agent name."""
    path = _task_dir(task_id) / "logs" / f"{agent}.log"
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_all_agent_logs(task_id: str, agent_names: list[str] | None = None) -> dict[str, str]:
    """Read all agent log files for a task. Returns {agent_name: content}."""
    if agent_names is None:
        logs_dir = _task_dir(task_id) / "logs"
        if not logs_dir.exists():
            return {}
        agent_names = [f.stem for f in logs_dir.iterdir() if f.suffix == ".log"]
    return {agent: read_agent_log(task_id, agent) for agent in agent_names}


def list_all_tasks(sort_desc: bool = True) -> list[dict]:
    """List all tasks by reading task_manifest.json files in outputs/.

    Args:
        sort_desc: If True, sort by task_id descending (newest first).
    """
    tasks = []
    if not OUTPUTS_DIR.exists():
        return tasks

    for task_dir in OUTPUTS_DIR.iterdir():
        if not task_dir.is_dir():
            continue
        manifest_path = task_dir / "task_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                tasks.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue

    tasks.sort(key=lambda t: t.get("start_time", ""), reverse=sort_desc)
    return tasks


def get_papers(task_id: str) -> list[dict]:
    """Read all data JSON files for a task (search results, filtered papers, gap analysis)."""
    data_dir = _task_dir(task_id) / "data"
    if not data_dir.exists():
        return []
    result = []
    for f in data_dir.iterdir():
        if f.suffix == ".json":
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    result.append({"name": f.stem, "data": json.load(fp)})
            except (json.JSONDecodeError, IOError):
                continue
    return result


def get_data_file(task_id: str, name: str) -> dict:
    """Read a specific data JSON file by name (without .json extension)."""
    path = _task_dir(task_id) / "data" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {name} for task {task_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_task(task_id: str) -> None:
    """Delete a task directory and all its contents."""
    import shutil
    task_path = _task_dir(task_id)
    if task_path.exists():
        shutil.rmtree(task_path)


def task_exists(task_id: str) -> bool:
    """Check if a task directory exists."""
    return _manifest_path(task_id).exists()
