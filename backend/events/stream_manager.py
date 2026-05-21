"""SSE stream manager for real-time task event broadcasting."""
import asyncio
import json
import queue
import sys
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Map of task_id -> list of thread-safe queues (one per connected client)
_clients: dict[str, list[queue.Queue]] = defaultdict(list)
_clients_lock = threading.Lock()

# Buffered events before any client connects
_pending_events: dict[str, list[dict]] = defaultdict(list)
_pending_lock = threading.Lock()

# Global event loop reference
_main_loop: asyncio.AbstractEventLoop | None = None
_main_loop_set_at: str | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop, _main_loop_set_at
    _main_loop = loop
    _main_loop_set_at = datetime.now().isoformat()
    print(f"[stream_manager] Main event loop registered at {_main_loop_set_at}", file=sys.stderr)


def broadcast_event(task_id: str, event: dict[str, Any]) -> None:
    """Broadcast an event to all connected SSE clients for a task."""
    event_type = event.get("type", "unknown")
    payload = json.dumps(event, ensure_ascii=False, default=str)

    with _clients_lock:
        client_queues = list(_clients.get(task_id, []))

    print(f"[broadcast] task={task_id} type={event_type} clients={len(client_queues)} "
          f"pending_buf={sum(len(v) for v in _pending_events.values())} "
          f"loop_running={_main_loop is not None and _main_loop.is_running()}", file=sys.stderr)

    def _enqueue(q: queue.Queue, p: str) -> None:
        try:
            q.put_nowait(p)
            print(f"[broadcast] queued event {event_type} for client", file=sys.stderr)
        except Exception as ex:
            print(f"[broadcast] enqueue error: {ex}", file=sys.stderr)

    # Deliver to connected clients
    if client_queues:
        if _main_loop is not None and _main_loop.is_running():
            for q in client_queues:
                _main_loop.call_soon_threadsafe(_enqueue, q, payload)
        else:
            # Fallback: buffer for later
            with _pending_lock:
                _pending_events[task_id].append(payload)
            print(f"[broadcast] no loop, buffered to pending (buf size={len(_pending_events[task_id])})", file=sys.stderr)
    else:
        # No clients — always buffer
        with _pending_lock:
            _pending_events[task_id].append(payload)
        print(f"[broadcast] no clients, buffered (pending buf for {task_id}: {len(_pending_events[task_id])})", file=sys.stderr)


def _drain_pending_events(task_id: str) -> list[str]:
    """Atomically drain and return all buffered events for a task."""
    with _pending_lock:
        events = list(_pending_events.get(task_id, []))
        _pending_events[task_id].clear()
    return events


async def _sse_generator(task_id: str, q: queue.Queue):
    """Generate SSE events for a client, reading from a thread-safe queue."""
    try:
        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'type': 'connected', 'task_id': task_id})}\n\n"

        # Drain and send all buffered events that were emitted before this client connected
        pending = _drain_pending_events(task_id)
        for payload in pending:
            yield f"event: message\ndata: {payload}\n\n"

        while True:
            try:
                payload = await asyncio.wait_for(asyncio.to_thread(q.get, True), timeout=30.0)
                yield f"event: message\ndata: {payload}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive comment every 30s
                yield f": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        # Clean up client on disconnect
        with _clients_lock:
            if task_id in _clients:
                try:
                    _clients[task_id].remove(q)
                except ValueError:
                    pass
                if not _clients[task_id]:
                    del _clients[task_id]


@router.get("/{task_id}/stream")
async def stream_task_events(request: Request, task_id: str):
    """SSE endpoint for real-time task event streaming.

    Clients connect to this endpoint and receive events as they occur.
    Events include: crew_started, task_started, task_completed, tool_usage_started,
    tool_usage_finished, agent_execution_started, agent_execution_completed,
    and raw log messages.

    The connection stays open until the client disconnects or the task completes.
    """
    from backend.services import task_reader

    if not task_reader.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    q: queue.Queue = queue.Queue()

    # Register this client
    with _clients_lock:
        _clients[task_id].append(q)

    return StreamingResponse(
        _sse_generator(task_id, q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
