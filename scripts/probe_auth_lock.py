#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.agent_cli_manager import AgentCliManager  # noqa: E402
from server.services.runtime_profile import get_runtime_profile  # noqa: E402


ENGINE_CREDENTIAL_FILES: Dict[str, List[str]] = {
    "codex": [".codex/auth.json"],
    "gemini": [".gemini/google_accounts.json", ".gemini/oauth_creds.json"],
    "iflow": [".iflow/iflow_accounts.json", ".iflow/oauth_creds.json"],
}


def _timestamp_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_command(engine: str, cli_path: Path, prompt: str) -> List[str]:
    if engine == "gemini":
        return [str(cli_path), "--yolo", prompt]
    if engine == "codex":
        sandbox_flag = "--full-auto"
        if os.environ.get("LANDLOCK_ENABLED") == "0":
            sandbox_flag = "--yolo"
        return [str(cli_path), "exec", sandbox_flag, "--skip-git-repo-check", "--json", prompt]
    if engine == "iflow":
        return [str(cli_path), "--yolo", "-p", prompt]
    raise ValueError(f"Unsupported engine: {engine}")


async def _pump_stream(stream: asyncio.StreamReader, out_file: Path, sink: bytearray) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "ab") as f:
        while True:
            chunk = await stream.read(1024)
            if not chunk:
                break
            sink.extend(chunk)
            f.write(chunk)
            f.flush()


async def _probe_single_engine(
    engine: str,
    base_out_dir: Path,
    timeout_sec: int,
    prompt: str,
) -> None:
    out_dir = base_out_dir / engine
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"
    stdout_path = out_dir / "stdout.raw"
    stderr_path = out_dir / "stderr.raw"
    stdout_text_path = out_dir / "stdout.txt"
    stderr_text_path = out_dir / "stderr.txt"

    base_profile = get_runtime_profile()
    manager = AgentCliManager(base_profile)
    manager.ensure_layout()
    cli_path = manager.resolve_engine_command(engine)

    result = {
        "engine": engine,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "timeout_sec": timeout_sec,
        "cli_path": str(cli_path) if cli_path else None,
        "status": "unknown",
        "return_code": None,
        "timed_out": False,
        "error": None,
        "command": None,
        "agent_home": None,
    }

    if cli_path is None:
        result["status"] = "skipped_cli_not_found"
        meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    with tempfile.TemporaryDirectory(prefix=f"auth-probe-{engine}-") as tmp_home:
        agent_home = Path(tmp_home).resolve()
        profile = replace(base_profile, agent_home=agent_home)
        probe_manager = AgentCliManager(profile)
        probe_manager.ensure_layout()
        result["agent_home"] = str(agent_home)

        # Make sure auth files are absent to force unauthenticated behavior.
        for rel in ENGINE_CREDENTIAL_FILES.get(engine, []):
            path = agent_home / rel
            if path.exists():
                path.unlink()

        env = profile.build_subprocess_env(os.environ.copy())
        cmd = _build_command(engine, cli_path, prompt)
        result["command"] = cmd

        stdout_bytes = bytearray()
        stderr_bytes = bytearray()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(ROOT),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout_task = asyncio.create_task(_pump_stream(proc.stdout, stdout_path, stdout_bytes))
            stderr_task = asyncio.create_task(_pump_stream(proc.stderr, stderr_path, stderr_bytes))

            try:
                await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
            except asyncio.TimeoutError:
                result["timed_out"] = True
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception:
                    proc.kill()
                    await proc.wait()

            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            result["return_code"] = proc.returncode
            result["status"] = "timed_out" if result["timed_out"] else "exited"
        except Exception as exc:
            result["status"] = "failed_to_launch"
            result["error"] = str(exc)

        stdout_text_path.write_text(stdout_bytes.decode("utf-8", errors="replace"), encoding="utf-8")
        stderr_text_path.write_text(stderr_bytes.decode("utf-8", errors="replace"), encoding="utf-8")

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe engine auth-lock output in managed runtime")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["gemini", "codex", "iflow"],
        choices=["gemini", "codex", "iflow"],
        help="Engines to probe",
    )
    parser.add_argument("--timeout", type=int, default=45, help="Per-engine timeout seconds")
    parser.add_argument(
        "--prompt",
        type=str,
        default="Please output a short JSON object with a single key named status.",
        help="Prompt used for probe execution",
    )
    args = parser.parse_args()

    profile = get_runtime_profile()
    out_dir = profile.data_dir / "auth_probe" / _timestamp_id()
    out_dir.mkdir(parents=True, exist_ok=True)

    for engine in args.engines:
        await _probe_single_engine(
            engine=engine,
            base_out_dir=out_dir,
            timeout_sec=args.timeout,
            prompt=args.prompt,
        )

    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
