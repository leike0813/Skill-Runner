from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ClaudeAuthCliSession:
    session_id: str
    process: subprocess.Popen[str]
    output_path: Path
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    status: str = "starting"
    auth_url: str | None = None
    error: str | None = None
    exit_code: int | None = None


class ClaudeAuthCliFlow:
    def start_session(
        self,
        *,
        session_id: str,
        command_path: Path,
        cwd: Path,
        env: dict[str, str],
        output_path: Path,
        expires_at: datetime,
    ) -> ClaudeAuthCliSession:
        with output_path.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(
                [str(command_path), "auth", "login"],
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        now = _utc_now()
        return ClaudeAuthCliSession(
            session_id=session_id,
            process=process,
            output_path=output_path,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )

    def refresh(self, session: ClaudeAuthCliSession) -> None:
        now = _utc_now()
        session.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            return
        if now > session.expires_at:
            self.cancel(session)
            session.status = "expired"
            session.error = "Auth session expired"
            return
        text = ""
        try:
            text = session.output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if "If the browser didn't open, visit:" in text:
            marker = "If the browser didn't open, visit:"
            tail = text.split(marker)[-1].strip()
            first_line = tail.splitlines()[0].strip() if tail else ""
            if first_line:
                session.auth_url = first_line
                if session.status == "starting":
                    session.status = "waiting_user"
        rc = session.process.poll()
        if rc is None:
            return
        session.exit_code = rc
        if rc == 0:
            session.status = "succeeded"
            session.error = None
        else:
            session.status = "failed"
            session.error = f"claude auth login exited with code {rc}"

    def cancel(self, session: ClaudeAuthCliSession) -> None:
        if session.status in _TERMINAL_STATUSES:
            return
        try:
            session.process.terminate()
        except OSError:
            pass
        session.status = "canceled"
        session.updated_at = _utc_now()
