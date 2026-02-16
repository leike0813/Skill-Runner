import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]

logger = logging.getLogger("run_local_e2e")


def _setup_logging(verbose: int) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _has_base_url(passthrough: list[str]) -> bool:
    return "--base-url" in passthrough


def _service_healthy(base_url: str) -> bool:
    url = f"{base_url.rstrip('/')}/"
    try:
        with httpx.Client(timeout=2.0) as client:
            res = client.get(url)
            return res.status_code == 200
    except httpx.HTTPError:
        return False


def _wait_service_ready(base_url: str, timeout_sec: int, deploy_proc: subprocess.Popen[bytes]) -> None:
    deadline = time.time() + timeout_sec
    url = f"{base_url.rstrip('/')}/"
    client = httpx.Client(timeout=2.0)
    try:
        while time.time() < deadline:
            if deploy_proc.poll() is not None:
                raise RuntimeError(
                    f"Local deploy process exited early with code {deploy_proc.returncode}"
                )
            try:
                res = client.get(url)
                if res.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(1)
    finally:
        client.close()
    raise RuntimeError(f"Service did not become ready within {timeout_sec}s: {base_url}")


def _wait_service_stopped(base_url: str, timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not _service_healthy(base_url):
            return True
        time.sleep(1)
    return False


def _stop_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return

    # deploy_local.sh ultimately launches uvicorn; stop the whole process group to avoid leaks.
    used_group_signal = False
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        used_group_signal = True
    except ProcessLookupError:
        return
    except Exception:
        proc.terminate()

    try:
        proc.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass

    if used_group_signal:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except Exception:
            proc.kill()
    else:
        proc.kill()

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("Deploy process did not exit after SIGKILL.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Local E2E Tests: start local deploy chain then run container-style E2E against it."
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="Target service base URL")
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=120,
        help="Seconds to wait for local service readiness",
    )
    parser.add_argument(
        "--deploy-script",
        default="scripts/deploy_local.sh",
        help="Local deploy script path (relative to repo root)",
    )
    parser.add_argument(
        "--keep-server",
        action="store_true",
        help="Do not stop local deploy process after tests",
    )
    parser.add_argument(
        "--reuse-existing-service",
        action="store_true",
        help="Reuse an already-running service at --base-url (disables default fail-fast).",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbose output")
    args, passthrough = parser.parse_known_args()

    _setup_logging(args.verbose)

    deploy_script = (PROJECT_ROOT / args.deploy_script).resolve()
    if not deploy_script.exists():
        raise RuntimeError(f"Deploy script not found: {deploy_script}")

    env = os.environ.copy()
    env.setdefault("SKILL_RUNNER_RUNTIME_MODE", "local")
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = (
        f"{PROJECT_ROOT}:{existing_pythonpath}" if existing_pythonpath else str(PROJECT_ROOT)
    )

    deploy_proc: subprocess.Popen[bytes] | None = None
    started_deploy = False
    if _service_healthy(args.base_url):
        if not args.reuse_existing_service:
            raise RuntimeError(
                f"Fail-fast: service already responding at {args.base_url}. "
                "Stop the existing service first, or pass --reuse-existing-service explicitly."
            )
        logger.warning(
            "Reusing existing service at %s (--reuse-existing-service). "
            "This run will not manage that service lifecycle.",
            args.base_url,
        )
    else:
        logger.info("Starting local deploy via: %s", deploy_script)
        deploy_proc = subprocess.Popen(
            ["bash", str(deploy_script)],
            cwd=str(PROJECT_ROOT),
            env=env,
            start_new_session=True,
        )
        started_deploy = True

    try:
        if started_deploy and deploy_proc is not None:
            _wait_service_ready(args.base_url, args.startup_timeout, deploy_proc)
        logger.info("Service is ready: %s", args.base_url)

        cmd = ["uv", "run", "--extra", "dev", "python", "tests/e2e/run_container_e2e_tests.py"]
        if not _has_base_url(passthrough):
            cmd.extend(["--base-url", args.base_url])
        if args.verbose:
            cmd.append("-" + ("v" * args.verbose))
        cmd.extend(passthrough)

        logger.info("Executing: %s", " ".join(cmd))
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, check=False)
        return result.returncode
    finally:
        if args.keep_server:
            logger.info("Keeping local deploy process alive (--keep-server).")
        else:
            if started_deploy and deploy_proc is not None:
                logger.info("Stopping local deploy process.")
                _stop_process(deploy_proc)
                if not _wait_service_stopped(args.base_url, timeout_sec=15):
                    logger.warning(
                        "Service at %s is still responding after cleanup; "
                        "there may be an external or leaked process.",
                        args.base_url,
                    )
            else:
                logger.info("No local deploy process was started; skipping service cleanup.")


if __name__ == "__main__":
    raise SystemExit(main())
