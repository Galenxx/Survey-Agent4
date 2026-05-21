"""Background crew execution service using threading + CrewAI event bus."""
import sys
import threading
import traceback
import os
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from src.storage.task_storage import TaskStorage

_DBG_LOG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_debug_executor.log"))


def _dbg(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(_DBG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception as ex:
        print(f"[_dbg write error: {ex}]", flush=True)

_running_tasks: dict[str, threading.Thread] = {}
_executor_lock = threading.Lock()

# Thread-local storage: current agent context (set when agent starts, cleared when done)
_thread_local = threading.local()

def _set_current_agent(task_id: str, agent_key: str) -> None:
    _thread_local.current_task_id = task_id
    _thread_local.current_agent_key = agent_key

def _get_current_agent_context() -> tuple[Optional[str], Optional[str]]:
    return getattr(_thread_local, 'current_task_id', None), getattr(_thread_local, 'current_agent_key', None)

def _clear_current_agent() -> None:
    _thread_local.current_task_id = None
    _thread_local.current_agent_key = None

# Track which agent is executing which crew task ID (task_id_str → agent_key)
# This is needed because in hierarchical mode, tool events carry the manager's role,
# so we must look up the correct agent by the task being executed.
_task_to_agent_map: dict[str, str] = {}
_task_map_lock = threading.Lock()

# SSE broadcaster passed from the app
_sse_broadcaster: Optional[Callable[[str, dict], None]] = None


def _set_task_agent_mapping(crew_task_id: str, agent_key: str) -> None:
    with _task_map_lock:
        _task_to_agent_map[crew_task_id] = agent_key


def _get_agent_for_task(crew_task_id: str) -> str:
    with _task_map_lock:
        return _task_to_agent_map.get(crew_task_id, "")


def _clear_task_agent_mapping(crew_task_id: str) -> None:
    with _task_map_lock:
        _task_to_agent_map.pop(crew_task_id, None)


def set_sse_broadcaster(broadcaster: Callable[[str, dict], None]) -> None:
    global _sse_broadcaster
    _sse_broadcaster = broadcaster


def broadcast_event(task_id: str, event_type: str, data: dict) -> None:
    _dbg(f"broadcast_event called: task={task_id} type={event_type} broadcaster={'SET' if _sse_broadcaster else 'NONE'}")
    if _sse_broadcaster:
        _dbg(f"Broadcasting: task={task_id} type={event_type}")
        _sse_broadcaster(task_id, {"type": event_type, **data})
    else:
        _dbg(f"_sse_broadcaster is None, event {event_type} dropped")


def _broadcast_agent_log(
    task_id: str,
    agent_key: str,
    task_storage: Optional["TaskStorage"],
) -> None:
    """Broadcast the complete log file content for an agent after it finishes."""
    if not task_storage or not agent_key:
        return
    try:
        log_content = task_storage.read_agent_log(agent_key)
        broadcast_event(task_id, "agent_log", {
            "agent_key": agent_key,
            "log_content": log_content,
        })
    except Exception:
        pass


import json
import re
import threading
from typing import Any

_ROUTER_OUTPUT_KEY = "router_parsed_params"
# Module-level storage for parsed router params (thread-safe)
_router_params: dict[str, Any] = {}
_router_params_lock = threading.Lock()


def set_router_params(params: dict[str, Any]) -> None:
    with _router_params_lock:
        _router_params.clear()
        _router_params.update(params)


def get_router_params() -> dict[str, Any]:
    with _router_params_lock:
        return dict(_router_params)


def parse_router_output(raw_output: str) -> dict[str, Any]:
    """Extract JSON from router output and return parsed params dict."""
    # Try to find JSON block in the output
    try:
        # Try direct JSON parse first
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass

    # Try finding JSON in markdown code blocks
    patterns = [
        r'```(?:json)?\s*\n?(.*?)\n?```',
        r'\{[^{}]*"topic"[^{}]*\}',
    ]
    for pattern in patterns:
        m = re.search(pattern, raw_output, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0) if m.lastindex == 0 else m.group(1))
            except json.JSONDecodeError:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass

    # Fallback: try to extract individual fields with regex
    result = {}
    field_map = [
        ("topic", r'"topic"\s*:\s*"([^"]*)"'),
        ("search_query", r'"search_query"\s*:\s*"([^"]*)"'),
        ("gap_direction", r'"gap_direction"\s*:\s*"([^"]*)"'),
        ("time_range", r'"time_range"\s*:\s*"([^"]*)"'),
        ("max_results", r'"max_results"\s*:\s*(\d+)'),
    ]
    for field, pattern in field_map:
        m = re.search(pattern, raw_output)
        if m:
            val = m.group(1)
            result[field] = int(val) if field == "max_results" else val

    return result if result else {}


# Map CrewAI agent roles to our agent names
AGENT_ROLE_MAP = {
    "Research Query Router": "router",
    "Academic Paper Searcher": "searcher",
    "Paper Relevance Filter": "filter",
    "Research Gap Analyzer": "analyzer",
    "Report Synthesizer": "synthesizer",
}


def _agent_name_from_role(role: str) -> str:
    return AGENT_ROLE_MAP.get(role, "") or _agent_name_from_role_fuzzy(role)


def _agent_name_from_role_fuzzy(role: str) -> str:
    r = role.lower()
    if "router" in r or "query" in r: return "router"
    if "searcher" in r or "paper search" in r: return "searcher"
    if "filter" in r or "relevance" in r: return "filter"
    if "analyzer" in r or "gap" in r: return "analyzer"
    if "synthesizer" in r or "report" in r: return "synthesizer"
    if "manager" in r or "orchestrat" in r: return "manager"
    return ""


def _safe_str(val, maxlen=500) -> str:
    """Convert any value to a safe ASCII string, removing emoji and non-ASCII."""
    s = str(val)
    s = s.encode("ascii", "replace").decode("ascii")
    s = s.replace("\ufffd", " ")
    import re
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen]


def _safe_dict(d: dict, maxlen=500) -> dict:
    return {str(k): _safe_str(v, maxlen) for k, v in d.items()}


def _write_agent_log(
    task_storage: Optional["TaskStorage"],
    agent_name: str,
    category: str,
    message: str,
) -> None:
    """Write a log entry to TaskStorage if available."""
    if task_storage is None:
        return
    try:
        task_storage.log(agent_name, category, message)
    except Exception:
        pass


def _register_crew_event_handlers(task_id: str, task_storage: Optional["TaskStorage"] = None) -> None:
    from crewai.events.event_bus import crewai_event_bus
    from crewai.events.types.agent_events import (
        AgentExecutionCompletedEvent,
        AgentExecutionErrorEvent,
        AgentExecutionStartedEvent,
    )
    from crewai.events.types.crew_events import (
        CrewKickoffCompletedEvent,
        CrewKickoffFailedEvent,
        CrewKickoffStartedEvent,
    )
    from crewai.events.types.task_events import (
        TaskCompletedEvent,
        TaskFailedEvent,
        TaskStartedEvent,
    )
    from crewai.events.types.tool_usage_events import (
        ToolUsageErrorEvent,
        ToolUsageFinishedEvent,
        ToolUsageStartedEvent,
    )

    def _task_name(task) -> str:
        if not task:
            return "unknown_task"
        return getattr(task, "name", None) or getattr(task, "description", "unknown_task")[:100]

    def _on_crew_started(event: CrewKickoffStartedEvent) -> None:
        _dbg("_on_crew_started fired!")
        try:
            crew_name = _safe_str(getattr(event, "crew_name", "crew") or "crew")
            inputs = {}
            raw_inputs = getattr(event, "inputs", None)
            if raw_inputs and isinstance(raw_inputs, dict):
                inputs = {k: _safe_str(v, 200) for k, v in raw_inputs.items()}
            broadcast_event(task_id, "crew_started", {"crew_name": crew_name, "inputs": inputs})
        except Exception as e:
            _dbg(f"_on_crew_started EXCEPTION: {e}")

    def _on_crew_completed(event: CrewKickoffCompletedEvent) -> None:
        try:
            output = _safe_str(getattr(event, "output", "") or "", 500)
            broadcast_event(task_id, "crew_completed", {"output": output})
            # Broadcast all agent logs at the end
            if task_storage:
                for agent_key in ["router", "searcher", "filter", "analyzer", "synthesizer", "manager"]:
                    _broadcast_agent_log(task_id, agent_key, task_storage)
        except Exception:
            pass

    def _on_crew_failed(event: CrewKickoffFailedEvent) -> None:
        try:
            error = _safe_str(getattr(event, "error", "") or "", 500)
            broadcast_event(task_id, "crew_failed", {"error": error})
            # Broadcast all agent logs on failure too
            if task_storage:
                for agent_key in ["router", "searcher", "filter", "analyzer", "synthesizer", "manager"]:
                    _broadcast_agent_log(task_id, agent_key, task_storage)
        except Exception:
            pass

    def _on_task_started(event: TaskStartedEvent) -> None:
        try:
            task_id_attr = str(getattr(event, "task_id", "") or "")
            task_obj = getattr(event, "task", None)
            name = _safe_str(_task_name(task_obj))
            agent_key = ""
            if task_obj:
                task_agent = getattr(task_obj, "agent", None)
                if task_agent:
                    agent_role = getattr(task_agent, "role", "") or ""
                    agent_key = _agent_name_from_role(agent_role)
            if not agent_key:
                agent_key = _agent_name_from_role(name)
            if task_id_attr and agent_key:
                _set_task_agent_mapping(task_id_attr, agent_key)
            _dbg(f"task_started: task_id={task_id_attr} name={name} agent_key={agent_key}")
            broadcast_event(task_id, "task_started", {"task_id": task_id_attr, "task_name": name, "agent_key": agent_key})
        except Exception:
            pass

    def _on_task_completed(event: TaskCompletedEvent) -> None:
        try:
            task_id_attr = str(getattr(event, "task_id", "") or "")
            name = _safe_str(_task_name(getattr(event, "task", None)))
            output = _safe_str(getattr(event, "output", "") or "", 500)
            agent_key = _get_agent_for_task(task_id_attr)

            # Parse router output and store parsed params for downstream tasks
            if agent_key == "router" and output:
                parsed = parse_router_output(output)
                if parsed:
                    _write_agent_log(task_storage, "router", "ROUTER_PARSED",
                        f"Parsed router params: {json.dumps(parsed, ensure_ascii=False)}")
                    # Store in module globals for downstream tools/agents to read
                    set_router_params(parsed)
                    # Broadcast the parsed params so the frontend can see them
                    broadcast_event(task_id, "router_params", parsed)

            broadcast_event(task_id, "task_completed", {"task_id": task_id_attr, "task_name": name, "output": output})
            # Clear the task→agent mapping now that the task is done
            if task_id_attr:
                _clear_task_agent_mapping(task_id_attr)
        except Exception:
            pass

    def _on_task_failed(event: TaskFailedEvent) -> None:
        try:
            task_id_attr = str(getattr(event, "task_id", "") or "")
            name = _safe_str(_task_name(getattr(event, "task", None)))
            error = _safe_str(getattr(event, "error", "") or "", 500)
            broadcast_event(task_id, "task_failed", {"task_id": task_id_attr, "task_name": name, "error": error})
        except Exception:
            pass

    def _on_agent_started(event: AgentExecutionStartedEvent) -> None:
        try:
            agent = getattr(event, "agent", None)
            role = _safe_str(getattr(agent, "role", "") or "") if agent else ""
            agent_key = _agent_name_from_role(role)
            name = _safe_str(_task_name(getattr(event, "task", None)))
            prompt = _safe_str(getattr(event, "prompt", "") or "", 1000)
            _set_current_agent(task_id, agent_key)
            broadcast_event(task_id, "agent_started", {
                "agent_role": role,
                "agent_key": agent_key,
                "task_name": name,
                "prompt": prompt,
            })
            if agent_key:
                _write_agent_log(task_storage, agent_key, "AGENT_STARTED",
                    f"Agent started: {role} | Task: {name}")
                if prompt:
                    _write_agent_log(task_storage, agent_key, "AGENT_PROMPT",
                        f"Prompt:\n{prompt[:2000]}{'... (truncated)' if len(prompt) > 2000 else ''}")
        except Exception:
            pass

    def _on_agent_completed(event: AgentExecutionCompletedEvent) -> None:
        try:
            agent = getattr(event, "agent", None)
            role = _safe_str(getattr(agent, "role", "") or "") if agent else ""
            agent_key = _agent_name_from_role(role)
            name = _safe_str(_task_name(getattr(event, "task", None)))
            output = _safe_str(getattr(event, "output", "") or "", 2000)
            broadcast_event(task_id, "agent_completed", {
                "agent_role": role,
                "agent_key": agent_key,
                "task_name": name,
                "output": output,
            })
            if agent_key:
                _write_agent_log(task_storage, agent_key, "AGENT_COMPLETED",
                    f"Agent completed: {role} | Task: {name}")
                if output:
                    _write_agent_log(task_storage, agent_key, "AGENT_OUTPUT",
                        f"Output:\n{output[:3000]}{'... (truncated)' if len(output) > 3000 else ''}")
            _broadcast_agent_log(task_id, agent_key, task_storage)
        except Exception:
            pass
        finally:
            _clear_current_agent()

    def _on_agent_error(event: AgentExecutionErrorEvent) -> None:
        try:
            agent = getattr(event, "agent", None)
            role = _safe_str(getattr(agent, "role", "") or "") if agent else ""
            agent_key = _agent_name_from_role(role)
            name = _safe_str(_task_name(getattr(event, "task", None)))
            error = _safe_str(getattr(event, "error", "") or "", 300)
            broadcast_event(task_id, "agent_error", {
                "agent_role": role,
                "agent_key": agent_key,
                "task_name": name,
                "error": error,
            })
            if agent_key:
                _write_agent_log(task_storage, agent_key, "AGENT_ERROR", f"Agent error: {role} | Task: {name} | Error: {error}")
            _broadcast_agent_log(task_id, agent_key, task_storage)
        except Exception:
            pass

    def _on_tool_started(event: ToolUsageStartedEvent) -> None:
        try:
            tool_name = _safe_str(getattr(event, "tool_name", "") or "", 100)
            event_task_id = str(getattr(event, "task_id", "") or "")
            agent_role = _safe_str(getattr(event, "agent_role", "") or "")
            if not agent_role:
                agent = getattr(event, "agent", None)
                agent_role = _safe_str(getattr(agent, "role", "") or "") if agent else ""
            agent_key = _get_agent_for_task(event_task_id)
            if not agent_key:
                agent_key = _agent_name_from_role(agent_role)
            task_n = _safe_str(getattr(event, "task_name", "") or "")
            raw_args = getattr(event, "tool_args", {})
            tool_args = _safe_dict(raw_args if isinstance(raw_args, dict) else {}, 500)
            input_data = getattr(event, "input", None)
            input_str = _safe_str(str(input_data), 2000) if input_data else ""
            broadcast_event(task_id, "tool_started", {
                "agent_role": agent_role,
                "agent_key": agent_key,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "task_name": task_n,
                "crew_task_id": event_task_id,
                "input": input_str,
            })
            if agent_key:
                args_str = ", ".join(f"{k}={v}" for k, v in tool_args.items())
                _write_agent_log(task_storage, agent_key, "TOOL_STARTED",
                    f"Tool: {tool_name} | Args: {args_str}")
                if input_str:
                    _write_agent_log(task_storage, agent_key, "TOOL_INPUT",
                        f"Tool Input:\n{input_str[:2000]}{'... (truncated)' if len(input_str) > 2000 else ''}")
        except Exception:
            pass

    def _on_tool_finished(event: ToolUsageFinishedEvent) -> None:
        try:
            tool_name = _safe_str(getattr(event, "tool_name", "") or "", 100)
            event_task_id = str(getattr(event, "task_id", "") or "")
            agent_role = _safe_str(getattr(event, "agent_role", "") or "")
            if not agent_role:
                agent = getattr(event, "agent", None)
                agent_role = _safe_str(getattr(agent, "role", "") or "") if agent else ""
            agent_key = _get_agent_for_task(event_task_id)
            if not agent_key:
                agent_key = _agent_name_from_role(agent_role)
            task_n = _safe_str(getattr(event, "task_name", "") or "")
            output = _safe_str(getattr(event, "output", "") or "", 2000)
            from_cache = bool(getattr(event, "from_cache", False))
            broadcast_event(task_id, "tool_finished", {
                "agent_role": agent_role,
                "agent_key": agent_key,
                "tool_name": tool_name,
                "output": output,
                "task_name": task_n,
                "from_cache": from_cache,
                "crew_task_id": event_task_id,
            })
            if agent_key:
                cached_str = "(cached) " if from_cache else ""
                _write_agent_log(task_storage, agent_key, "TOOL_FINISHED",
                    f"{cached_str}Tool: {tool_name} | Result:\n{output[:3000]}{'... (truncated)' if len(output) > 3000 else ''}")
        except Exception:
            pass

    def _on_tool_error(event: ToolUsageErrorEvent) -> None:
        try:
            tool_name = _safe_str(getattr(event, "tool_name", "") or "", 100)
            event_task_id = str(getattr(event, "task_id", "") or "")
            agent_role = _safe_str(getattr(event, "agent_role", "") or "")
            if not agent_role:
                agent = getattr(event, "agent", None)
                agent_role = _safe_str(getattr(agent, "role", "") or "") if agent else ""
            # Resolve agent_key: prefer task→agent map (authoritative), fall back to role-based lookup
            agent_key = _get_agent_for_task(event_task_id)
            if not agent_key:
                agent_key = _agent_name_from_role(agent_role)
            task_n = _safe_str(getattr(event, "task_name", "") or "")
            error = _safe_str(getattr(event, "error", "") or "", 300)
            broadcast_event(task_id, "tool_error", {
                "agent_role": agent_role,
                "agent_key": agent_key,
                "tool_name": tool_name,
                "error": error,
                "task_name": task_n,
                "crew_task_id": event_task_id,
            })
            if agent_key:
                _write_agent_log(task_storage, agent_key, "TOOL_ERROR", f"Tool: {tool_name} | Error: {error}")
        except Exception:
            pass

    _dbg(f"Registering handlers for task={task_id}")

    bus = crewai_event_bus
    bus.on(CrewKickoffStartedEvent, _on_crew_started)
    bus.on(CrewKickoffCompletedEvent, _on_crew_completed)
    bus.on(CrewKickoffFailedEvent, _on_crew_failed)
    bus.on(TaskStartedEvent, _on_task_started)
    bus.on(TaskCompletedEvent, _on_task_completed)
    bus.on(TaskFailedEvent, _on_task_failed)
    bus.on(AgentExecutionStartedEvent, _on_agent_started)
    bus.on(AgentExecutionCompletedEvent, _on_agent_completed)
    bus.on(AgentExecutionErrorEvent, _on_agent_error)
    bus.on(ToolUsageStartedEvent, _on_tool_started)
    bus.on(ToolUsageFinishedEvent, _on_tool_finished)
    bus.on(ToolUsageErrorEvent, _on_tool_error)
    _dbg(f"All handlers registered. Bus state: {type(bus).__name__}")


def _patch_printer_for_utf8():
    """Patch crewai_core PRINTER to handle GBK encoding errors on Windows."""
    try:
        from crewai_core.printer import PRINTER as _orig_printer
        import sys

        class _SafePrinter:
            """Wrapper that retries PRINTER.print with UTF-8 encoding on failure."""

            @staticmethod
            def print(*args, file=None, **kwargs):
                try:
                    _orig_printer.print(*args, file=file, **kwargs)
                except UnicodeEncodeError:
                    if file is None:
                        file = sys.stdout
                    try:
                        file.reconfigure(encoding="utf-8", errors="replace")
                    except Exception:
                        pass
                    _orig_printer.print(*args, file=file, **kwargs)

        # Monkey-patch in place
        import crewai_core.printer
        crewai_core.printer.PRINTER = _SafePrinter
    except Exception:
        pass


def _run_crew_task(task_id: str, task_storage: "TaskStorage") -> None:
    """Inner function running in the background thread."""
    import sys
    _dbg(f"_run_crew_task STARTING for {task_id}")
    try:
        from dotenv import load_dotenv
        from pathlib import Path

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")

        _dbg("patching printer...")
        _patch_printer_for_utf8()
        _dbg("importing tool_wrapper...")

        from src.storage.tool_wrapper import set_global_broadcaster
        _dbg("setting global broadcaster...")
        set_global_broadcaster(broadcast_event)
        _dbg(f"broadcaster set: {_sse_broadcaster is not None}")

        _dbg("importing crew...")
        from src.crews.research_gap_crew import run_research_gap_analysis

        _dbg("registering handlers...")
        _register_crew_event_handlers(task_id, task_storage)

        _dbg("running crew...")
        run_research_gap_analysis(
            user_input=task_storage.task_name,
            task_storage=task_storage,
        )
        _dbg("crew finished normally")
    except Exception as e:
        _dbg(f"Task FAILED: {e}")
        _dbg(traceback.format_exc())
        sys.stderr.write(f"[crew_executor] Task {task_id} failed: {e}\n")
        sys.stderr.write(traceback.format_exc())
        sys.stderr.flush()
    finally:
        with _executor_lock:
            _running_tasks.pop(task_id, None)


def start_task(task_storage: "TaskStorage", output_dir: Optional[str] = None) -> str:
    """Spawn a background thread running the research gap analysis crew."""
    task_id = task_storage.task_id
    _dbg(f"start_task called with task_id={task_id}")
    thread = threading.Thread(target=_run_crew_task, args=(task_id, task_storage), daemon=True)
    with _executor_lock:
        _running_tasks[task_id] = thread
    thread.start()
    _dbg(f"thread started for task_id={task_id}")
    return task_id


def is_running(task_id: str) -> bool:
    with _executor_lock:
        return task_id in _running_tasks


def get_running_tasks() -> dict[str, threading.Thread]:
    with _executor_lock:
        return dict(_running_tasks)


def cancel_task(task_id: str) -> bool:
    with _executor_lock:
        thread = _running_tasks.get(task_id)
    if thread is None:
        return False
    thread.join(timeout=5.0)
    with _executor_lock:
        _running_tasks.pop(task_id, None)
    return not thread.is_alive()
