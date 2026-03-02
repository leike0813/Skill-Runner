from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Dict, Protocol


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class TransportLogPaths:
    transport: str
    session_id: str
    root: Path
    events_path: Path
    primary_log_path: Path
    secondary_log_path: Path | None = None
    persisted: bool = True


class AuthSessionLogWriter(Protocol):
    def init_paths(self, *, transport: str, session_id: str) -> TransportLogPaths:
        ...

    def append_event(
        self,
        paths: TransportLogPaths,
        event_type: str,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        ...

    def cleanup_paths(self, paths: TransportLogPaths) -> None:
        ...


class AuthLogWriter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def init_paths(self, *, transport: str, session_id: str) -> TransportLogPaths:
        normalized = transport.strip().lower()
        session_root = self.root / normalized / session_id
        session_root.mkdir(parents=True, exist_ok=True)
        events_path = session_root / "events.jsonl"
        events_path.touch(exist_ok=True)
        if normalized == "oauth_proxy":
            primary = session_root / "http_trace.log"
            primary.touch(exist_ok=True)
            return TransportLogPaths(
                transport=normalized,
                session_id=session_id,
                root=session_root,
                events_path=events_path,
                primary_log_path=primary,
                secondary_log_path=None,
                persisted=True,
            )
        primary = session_root / "pty.log"
        secondary = session_root / "stdin.log"
        primary.touch(exist_ok=True)
        secondary.touch(exist_ok=True)
        return TransportLogPaths(
            transport=normalized,
            session_id=session_id,
            root=session_root,
            events_path=events_path,
            primary_log_path=primary,
            secondary_log_path=secondary,
            persisted=True,
        )

    def append_event(
        self,
        paths: TransportLogPaths,
        event_type: str,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        data = {
            "ts": _utc_iso_now(),
            "type": event_type,
            "transport": paths.transport,
            "session_id": paths.session_id,
        }
        if payload:
            data.update(payload)
        with paths.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def cleanup_paths(self, paths: TransportLogPaths) -> None:
        _ = paths


class NoopAuthLogWriter:
    """Auth log writer that avoids persistent data-dir logging by using ephemeral files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def init_paths(self, *, transport: str, session_id: str) -> TransportLogPaths:
        normalized = transport.strip().lower()
        session_root = Path(
            tempfile.mkdtemp(
                prefix=f"{normalized}-{session_id}-",
                dir=str(self.root),
            )
        )
        events_path = session_root / "events.jsonl"
        if normalized == "oauth_proxy":
            primary = session_root / "http_trace.log"
            primary.touch(exist_ok=True)
            return TransportLogPaths(
                transport=normalized,
                session_id=session_id,
                root=session_root,
                events_path=events_path,
                primary_log_path=primary,
                secondary_log_path=None,
                persisted=False,
            )

        primary = session_root / "pty.log"
        secondary = session_root / "stdin.log"
        primary.touch(exist_ok=True)
        secondary.touch(exist_ok=True)
        return TransportLogPaths(
            transport=normalized,
            session_id=session_id,
            root=session_root,
            events_path=events_path,
            primary_log_path=primary,
            secondary_log_path=secondary,
            persisted=False,
        )

    def append_event(
        self,
        paths: TransportLogPaths,
        event_type: str,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        _ = (paths, event_type, payload)

    def cleanup_paths(self, paths: TransportLogPaths) -> None:
        try:
            shutil.rmtree(paths.root)
        except OSError:
            return
