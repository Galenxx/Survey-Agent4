"""Tool wrapper that auto-logs tool execution to the current agent's log file.

Each tool is wrapped with an agent key and TaskStorage. The wrapper intercepts
_run() calls and writes tool input/output to the agent's log file, then
broadcasts the complete log via SSE.
"""
import threading
import re
from datetime import datetime
from typing import Any, Callable, Optional


# Thread-local storage: current agent context
_thread_local = threading.local()
_global_broadcaster: Optional[Callable[[str, dict], None]] = None
_broadcaster_lock = threading.Lock()


def set_agent_context(task_id: str, agent_key: str) -> None:
    """Set the current agent context for the running thread."""
    _thread_local.task_id = task_id
    _thread_local.agent_key = agent_key


def clear_agent_context() -> None:
    """Clear the current agent context."""
    _thread_local.task_id = None
    _thread_local.agent_key = None


def get_agent_context() -> tuple[Optional[str], Optional[str]]:
    """Return (task_id, agent_key) for the current thread."""
    return getattr(_thread_local, 'task_id', None), getattr(_thread_local, 'agent_key', None)


def set_global_broadcaster(broadcaster: Callable[[str, dict], None]) -> None:
    """Set the global SSE broadcaster."""
    global _global_broadcaster
    with _broadcaster_lock:
        _global_broadcaster = broadcaster


def _get_broadcaster() -> Optional[Callable[[str, dict], None]]:
    """Get the current broadcaster, trying crew_executor as fallback."""
    global _global_broadcaster
    if _global_broadcaster:
        return _global_broadcaster
    # Try to import from crew_executor (safe - it's module-level)
    try:
        from backend.services.crew_executor import _sse_broadcaster as bs
        return bs
    except Exception:
        return None


def _broadcast_agent_log(task_id: str, agent_key: str, log_content: str) -> None:
    """Broadcast the complete log content for an agent via SSE."""
    broadcaster = _get_broadcaster()
    if broadcaster and task_id and agent_key:
        try:
            broadcaster(task_id, {
                "type": "agent_log",
                "agent_key": agent_key,
                "log_content": log_content,
            })
        except Exception:
            pass


def _truncate(s: str, maxlen: int = 2000) -> str:
    if len(s) <= maxlen:
        return s
    return s[:maxlen] + f"\n... (truncated, {len(s) - maxlen} chars omitted)"


def _safe_str(val: Any, maxlen: int = 500) -> str:
    s = str(val)
    s = s.encode("ascii", "replace").decode("ascii")
    s = s.replace("\ufffd", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen]


def _build_args_dict(original_run: Callable, args: tuple, kwargs: dict) -> dict:
    try:
        import inspect
        sig = inspect.signature(original_run)
        param_names = list(sig.parameters.keys())
        if param_names and param_names[0] in ('self',):
            param_names = param_names[1:]
        args_dict = {}
        for i, val in enumerate(args):
            if i < len(param_names):
                args_dict[param_names[i]] = val
            else:
                args_dict[f"arg{i}"] = val
        for k, v in kwargs.items():
            args_dict[k] = v
        return args_dict
    except Exception:
        return {"args": str(args)[:200], "kwargs": str(kwargs)[:200]}


def _log_tool_execution(
    task_storage: Any,
    agent_key: str,
    tool_name: str,
    args: dict,
    output: str,
    error: Optional[str],
) -> None:
    """Write tool execution to agent log file and broadcast via SSE."""
    if not agent_key:
        return
    task_id, _ = get_agent_context()
    args_str = ", ".join(f"{k}={_safe_str(v, 100)}" for k, v in args.items())

    if task_storage:
        try:
            if error:
                entry = f"{tool_name}({args_str}) ERROR: {error}"
                task_storage.log(agent_key, "TOOL_ERROR", entry)
            else:
                task_storage.log(agent_key, "TOOL_STARTED", f"{tool_name}({args_str})")
                task_storage.log(agent_key, "TOOL_OUTPUT", f"{tool_name} result:\n{_truncate(output, 3000)}")

            if task_id:
                log_content = task_storage.read_agent_log(agent_key)
                _broadcast_agent_log(task_id, agent_key, log_content)
        except Exception:
            pass
    elif task_id:
        entry = f"[TOOL] {tool_name}({args_str})"
        if error:
            entry += f" ERROR: {error}"
        _broadcast_agent_log(task_id, agent_key, entry)


def wrap_tool_for_logging(tool: Any, agent_key: str, task_storage: Any) -> Any:
    """Wrap a CrewAI tool so every _run() call auto-logs to the agent's log file.

    Args:
        tool: The BaseTool instance to wrap.
        agent_key: The agent name (e.g. "router", "searcher").
        task_storage: TaskStorage instance for writing logs to disk.

    Returns:
        The same tool instance, but with _run intercepted for logging.
    """
    original_run = tool._run

    def logged_run(*args: Any, **kwargs: Any) -> str:
        tool_name = getattr(tool, 'name', None) or getattr(tool, '__class__.__name__', 'UnknownTool')
        args_dict = _build_args_dict(original_run, args, kwargs)

        # Inject output_dir for pdf_download if not provided
        if tool_name == "pdf_download" and task_storage:
            if not args_dict.get('output_dir'):
                args_dict['output_dir'] = task_storage.get_papers_dir()

        # Truncate large values for display
        display_args = {k: (_truncate(v, 300) if isinstance(v, str) else v) for k, v in args_dict.items()}

        try:
            result = original_run(*args, **kwargs)
            _log_tool_execution(task_storage, agent_key, tool_name, display_args, result, None)
            return result
        except Exception as e:
            _log_tool_execution(task_storage, agent_key, tool_name, display_args, "", f"{type(e).__name__}: {e}")
            raise

    tool._run = logged_run
    return tool
