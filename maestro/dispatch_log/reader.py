"""
Dispatch log reader (T3.3).

Provides a one-shot scan and a tail-mode generator for the dispatch
event log. Tracks (inode, offset) so rotation produces no event loss;
holds back partial lines so a mid-write read never yields a torn event.
"""

import threading
import time
import warnings
from pathlib import Path
from typing import Iterator, Optional

from maestro.dispatch_log.events import DispatchEvent, DISPATCH_EVENT_ADAPTER


def scan_log(path: Path) -> list[DispatchEvent]:
    """Return all events in insertion order; skip unparseable lines with a warning.

    Missing file is treated as no-events-yet (returns []) so the UI can
    load before any dispatch has happened."""
    if not path.exists():
        return []
    events: list[DispatchEvent] = []
    raw = path.read_bytes()
    for line in raw.split(b"\n"):
        if not line:
            continue
        try:
            events.append(DISPATCH_EVENT_ADAPTER.validate_json(line))
        except Exception as e:
            warnings.warn(
                f"dispatch log: skipping unparseable line: {e}",
                RuntimeWarning,
                stacklevel=2,
            )
    return events


def tail_log(
    path: Path,
    *,
    poll_interval_s: float = 1.0,
    stop_event: Optional[threading.Event] = None,
) -> Iterator[DispatchEvent]:
    """Yield new events as they are appended; reopen cleanly on rotation.

    Polls os.stat at poll_interval_s. On inode change, resets offset to 0
    so events in the rotated-in file are not lost. Holds back the final
    partial line (no trailing newline) so a torn read never produces a
    bad event. Exits cleanly when stop_event is set."""
    inode: Optional[int] = None
    offset = 0
    buffer = b""

    def should_stop() -> bool:
        return stop_event is not None and stop_event.is_set()

    while not should_stop():
        try:
            st = path.stat()
        except FileNotFoundError:
            time.sleep(poll_interval_s)
            continue

        if inode is None or st.st_ino != inode:
            inode = st.st_ino
            offset = 0
            buffer = b""

        if st.st_size > offset:
            with open(path, "rb") as f:
                f.seek(offset)
                chunk = f.read(st.st_size - offset)
            offset = st.st_size
            buffer += chunk
            *complete, partial = buffer.split(b"\n")
            for line in complete:
                if not line:
                    continue
                try:
                    yield DISPATCH_EVENT_ADAPTER.validate_json(line)
                except Exception as e:
                    warnings.warn(
                        f"dispatch log: skipping unparseable line: {e}",
                        RuntimeWarning,
                        stacklevel=2,
                    )
            buffer = partial

        time.sleep(poll_interval_s)
