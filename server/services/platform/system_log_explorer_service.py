from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config import config

_TEXT_LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?P<logger>[^:]+):\s*"
    r"(?P<message>.*)$"
)
_KV_TOKEN_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>[^\s]+)")
_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_SOURCES = {"system", "bootstrap"}


@dataclass(frozen=True)
class ParsedLogRow:
    ts: str | None
    ts_dt: datetime | None
    level: str | None
    message: str
    raw: str
    source: str
    file: str
    line_no: int
    file_mtime: float


class SystemLogExplorerService:
    """Read-only log query service for management System Console."""

    def query(
        self,
        *,
        source: str,
        cursor: int,
        limit: int,
        q: str | None,
        level: str | None,
        from_ts: datetime | None,
        to_ts: datetime | None,
    ) -> dict[str, Any]:
        normalized_source = source.strip().lower()
        if normalized_source not in _VALID_SOURCES:
            raise ValueError("source must be one of: system, bootstrap")

        normalized_level = self._normalize_level(level)
        query_keyword = q.strip().lower() if isinstance(q, str) and q.strip() else None
        from_dt = self._normalize_filter_dt(from_ts)
        to_dt = self._normalize_filter_dt(to_ts)

        rows = self._load_rows(
            source=normalized_source,
            keyword=query_keyword,
            level=normalized_level,
            from_ts=from_dt,
            to_ts=to_dt,
        )
        total = len(rows)
        start = min(cursor, total)
        end = min(start + limit, total)
        page = rows[start:end]
        next_cursor = end if end < total else None
        return {
            "source": normalized_source,
            "items": [
                {
                    "ts": row.ts,
                    "level": row.level,
                    "message": row.message,
                    "raw": row.raw,
                    "source": row.source,
                    "file": row.file,
                    "line_no": row.line_no,
                }
                for row in page
            ],
            "next_cursor": next_cursor,
            "total_matched": total,
        }

    def _load_rows(
        self,
        *,
        source: str,
        keyword: str | None,
        level: str | None,
        from_ts: datetime | None,
        to_ts: datetime | None,
    ) -> list[ParsedLogRow]:
        files = self._resolve_log_family(source)
        rows: list[ParsedLogRow] = []
        for path in files:
            file_mtime = path.stat().st_mtime
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, raw_line in enumerate(content.splitlines(), start=1):
                raw = raw_line.rstrip("\n")
                if not raw:
                    continue
                parsed = self._parse_row(raw=raw, source=source, file=path.name, line_no=line_no, file_mtime=file_mtime)
                if level and parsed.level != level:
                    continue
                if keyword and keyword not in (parsed.message.lower() + "\n" + parsed.raw.lower()):
                    continue
                if from_ts is not None or to_ts is not None:
                    if parsed.ts_dt is None:
                        continue
                    if from_ts is not None and parsed.ts_dt < from_ts:
                        continue
                    if to_ts is not None and parsed.ts_dt > to_ts:
                        continue
                rows.append(parsed)

        rows.sort(
            key=lambda row: (
                1 if row.ts_dt is not None else 0,
                row.ts_dt.timestamp() if row.ts_dt is not None else 0.0,
                row.file_mtime,
                row.line_no,
            ),
            reverse=True,
        )
        return rows

    def _resolve_log_family(self, source: str) -> list[Path]:
        if source == "system":
            log_dir = Path(str(config.SYSTEM.LOGGING.DIR)).resolve()
            basename = str(config.SYSTEM.LOGGING.FILE_BASENAME).strip() or "skill_runner.log"
        else:
            log_dir = Path(str(config.SYSTEM.DATA_DIR)).resolve() / "logs"
            basename = "bootstrap.log"
        if not log_dir.exists():
            return []
        files: list[Path] = []
        family_prefix = f"{basename}."
        for path in log_dir.iterdir():
            if not path.is_file():
                continue
            if path.name == basename or path.name.startswith(family_prefix):
                files.append(path)
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return files

    def _parse_row(
        self,
        *,
        raw: str,
        source: str,
        file: str,
        line_no: int,
        file_mtime: float,
    ) -> ParsedLogRow:
        json_parsed = self._try_parse_json_line(raw)
        if json_parsed is not None:
            return ParsedLogRow(
                ts=json_parsed["ts"],
                ts_dt=json_parsed["ts_dt"],
                level=json_parsed["level"],
                message=json_parsed["message"],
                raw=raw,
                source=source,
                file=file,
                line_no=line_no,
                file_mtime=file_mtime,
            )
        text_match = _TEXT_LOG_RE.match(raw)
        if text_match:
            dt = datetime.strptime(text_match.group("ts"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            return ParsedLogRow(
                ts=dt.isoformat().replace("+00:00", "Z"),
                ts_dt=dt,
                level=self._normalize_level(text_match.group("level")),
                message=text_match.group("message").strip() or raw,
                raw=raw,
                source=source,
                file=file,
                line_no=line_no,
                file_mtime=file_mtime,
            )
        kv_payload = self._parse_kv_line(raw)
        kv_ts = self._try_parse_timestamp(kv_payload.get("ts")) if kv_payload else None
        kv_level = self._normalize_level(kv_payload.get("level")) if kv_payload else None
        if source == "bootstrap" and kv_level is None:
            kv_level = "INFO"
        message = ""
        if kv_payload:
            message = str(kv_payload.get("message") or kv_payload.get("event") or "").strip()
        if not message:
            message = raw
        return ParsedLogRow(
            ts=kv_ts[0] if kv_ts is not None else None,
            ts_dt=kv_ts[1] if kv_ts is not None else None,
            level=kv_level,
            message=message,
            raw=raw,
            source=source,
            file=file,
            line_no=line_no,
            file_mtime=file_mtime,
        )

    @staticmethod
    def _normalize_level(level: str | None) -> str | None:
        if not isinstance(level, str):
            return None
        normalized = level.strip().upper()
        if normalized in _VALID_LEVELS:
            return normalized
        return None

    @staticmethod
    def _normalize_filter_dt(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _try_parse_json_line(self, raw: str) -> dict[str, Any] | None:
        if not raw.startswith("{"):
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        ts_pair = self._try_parse_timestamp(payload.get("timestamp") or payload.get("ts"))
        level = self._normalize_level(payload.get("level"))
        message_raw = payload.get("message") or payload.get("msg")
        message = str(message_raw).strip() if message_raw is not None else ""
        if not message:
            message = raw
        return {
            "ts": ts_pair[0] if ts_pair is not None else None,
            "ts_dt": ts_pair[1] if ts_pair is not None else None,
            "level": level,
            "message": message,
        }

    @staticmethod
    def _parse_kv_line(raw: str) -> dict[str, str]:
        payload: dict[str, str] = {}
        for match in _KV_TOKEN_RE.finditer(raw):
            payload[match.group("key")] = match.group("value")
        return payload

    @staticmethod
    def _try_parse_timestamp(raw: Any) -> tuple[str, datetime] | None:
        if not isinstance(raw, str):
            return None
        value = raw.strip()
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z"), dt


system_log_explorer_service = SystemLogExplorerService()
