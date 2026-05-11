"""maestro/webui/dispatch_log_api.py — SSE stream of dispatch log events."""

import asyncio
import os
import threading
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from maestro.dispatch_log.reader import tail_log
from maestro.paths import dispatch_log_path

router = APIRouter(prefix="/api/dispatch_log", tags=["dispatch_log"])

_DEFAULT_POLL_INTERVAL_S = 1.0


def _log_file() -> Path:
    """Compose <project>/.maestro/logs/dispatch.jsonl from Path.cwd()."""
    return dispatch_log_path(Path.cwd()) / "dispatch.jsonl"


def _parse_last_event_id(raw: str | None) -> tuple[int, int] | None:
    """Parse <inode>:<offset>; return (inode, offset) or None if invalid."""
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


async def _async_tail(
    path: Path,
    last_event_id: tuple[int, int] | None,
    stop_event: threading.Event,
    poll_interval_s: float,
) -> AsyncIterator[dict]:
    """Bridge sync tail_log into an async SSE event stream.

    Runs tail_log in a background thread; surfaces yielded events via
    asyncio.Queue so the route handler stays cooperative."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    sentinel = object()
    seen_inode: int | None = None

    def runner():
        try:
            for event in tail_log(path, poll_interval_s=poll_interval_s, stop_event=stop_event):
                try:
                    st = os.stat(path)
                    inode = st.st_ino
                    offset = st.st_size
                except OSError:
                    inode, offset = -1, -1
                asyncio.run_coroutine_threadsafe(
                    queue.put((event, inode, offset)), loop
                )
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(sentinel), loop)

    t = threading.Thread(target=runner, daemon=True)
    t.start()

    while True:
        item = await queue.get()
        if item is sentinel:
            return
        event, inode, offset = item

        if seen_inode is None:
            # First event in stream. Emit rotated if client's last seen
            # inode differs from what we now observe — handles cold-start
            # rotation (file didn't exist at connect; appears later with
            # a different inode than client recorded).
            if last_event_id is not None and inode != last_event_id[0]:
                yield {"event": "rotated", "data": ""}
                last_event_id = None
        elif inode != seen_inode:
            yield {"event": "rotated", "data": ""}
        seen_inode = inode

        if last_event_id is not None:
            req_inode, req_offset = last_event_id
            if inode == req_inode and offset <= req_offset:
                continue
            last_event_id = None

        yield {
            "event": "dispatch_event",
            "id": f"{inode}:{offset}",
            "data": event.model_dump_json(),
        }


@router.get("/stream")
async def stream_dispatch_log(request: Request) -> EventSourceResponse:
    """Stream dispatch events as Server-Sent Events.

    Last-Event-ID header resumes after a previously delivered event.
    Inode change (file rotation) emits a synthetic `rotated` event."""
    last_event_id = _parse_last_event_id(request.headers.get("Last-Event-ID"))
    stop_event = threading.Event()
    poll_interval_s = _DEFAULT_POLL_INTERVAL_S

    path = _log_file()

    async def event_source():
        try:
            async for sse_dict in _async_tail(path, last_event_id, stop_event, poll_interval_s):
                if await request.is_disconnected():
                    break
                yield sse_dict
        finally:
            stop_event.set()

    return EventSourceResponse(event_source())
