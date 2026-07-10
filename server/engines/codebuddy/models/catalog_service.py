from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import config
from server.engines.codebuddy.auth.credential_store import CodeBuddyCredentialStore, codebuddy_credential_store
from server.engines.codebuddy.auth.provider_registry import CODEBUDDY_PROVIDER_IDS, require_provider
from server.services.engine_management.agent_cli_manager import AgentCliManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CodeBuddyModelCatalog:
    """Provider-partitioned, credential-backed CodeBuddy model probe cache."""

    def __init__(
        self,
        *,
        credential_store: CodeBuddyCredentialStore | None = None,
        cli_manager: AgentCliManager | None = None,
        cache_path: Path | None = None,
    ) -> None:
        self._credentials = credential_store or codebuddy_credential_store
        self._cli_manager = cli_manager or AgentCliManager()
        self._cache_path_override = cache_path
        self._lock = asyncio.Lock()

    def cache_path(self) -> Path:
        if self._cache_path_override is not None:
            return self._cache_path_override
        return Path(config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR) / "codebuddy" / "catalog.json"

    def _load(self) -> dict[str, Any]:
        path = self.cache_path()
        if not path.exists():
            return {"engine": "codebuddy", "providers": {}}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"engine": "codebuddy", "providers": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("providers"), dict):
            return {"engine": "codebuddy", "providers": {}}
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        path = self.cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def parse_models(help_text: str, provider_id: str) -> list[dict[str, Any]]:
        """Parse the CLI's ``--model`` Currently supported section without a static fallback."""
        marker = re.search(r"--model.*?(?:Currently supported|Supported models)\s*:?", help_text, re.I | re.S)
        section = help_text[marker.end():] if marker else help_text
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for line in section.splitlines():
            value = line.strip().lstrip("-*").strip()
            if not value or value.startswith("--"):
                if rows and value.startswith("--"):
                    break
                continue
            candidate = re.split(r"\s{2,}|\s+-\s+", value, maxsplit=1)[0].strip("` ")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", candidate) or candidate in seen:
                continue
            seen.add(candidate)
            rows.append({
                "id": f"{provider_id}/{candidate}",
                "provider": provider_id,
                "provider_id": provider_id,
                "model": candidate,
                "display_name": candidate,
                "deprecated": False,
                "notes": "runtime_probe_cache",
                "supported_effort": ["default"],
            })
        return rows

    async def _run(self, command: str | Path, args: list[str], env: dict[str, str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            str(command), *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
        )
        timeout = max(1, int(config.SYSTEM.ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC))
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise RuntimeError("codebuddy model probe timed out") from exc
        if proc.returncode != 0:
            raise RuntimeError(f"codebuddy {' '.join(args)} exited with code {proc.returncode}")
        return (stdout or b"").decode("utf-8", errors="replace")

    async def refresh_provider(self, provider_id: str) -> dict[str, Any]:
        provider = require_provider(provider_id)
        credential = self._credentials.get(provider.provider_id)
        if credential is None or self._credentials.project_status(provider.provider_id).credential_state != "present":
            raise RuntimeError(f"CodeBuddy credential unavailable for {provider.provider_id}")
        command = self._cli_manager.resolve_engine_command("codebuddy")
        if command is None:
            raise RuntimeError("CodeBuddy CLI not found in managed prefix")
        env = self._cli_manager.profile.build_subprocess_env()
        for key in ("CODEBUDDY_API_KEY", "CODEBUDDY_BASE_URL", "CODEBUDDY_AUTH_TOKEN", "CODEBUDDY_INTERNET_ENVIRONMENT", "CODEBUDDY_CONFIG_DIR"):
            env.pop(key, None)
        env.update({
            "CODEBUDDY_AUTH_TOKEN": credential.token,
            "CODEBUDDY_INTERNET_ENVIRONMENT": provider.runtime_environment,
            "CODEBUDDY_CONFIG_DIR": str(provider.config_dir(self._cli_manager.profile.agent_home)),
        })
        version, help_text = await asyncio.gather(self._run(command, ["--version"], env), self._run(command, ["--help"], env))
        models = self.parse_models(help_text, provider.provider_id)
        if not models:
            raise RuntimeError("codebuddy --help did not provide supported models")
        # Raw help is intentionally not persisted: it can contain user/account diagnostics.
        return {"status": "ready", "updated_at": _now(), "environment": provider.runtime_environment,
                "cli_version": version.strip(), "last_error": None, "models": models, "raw_help_ref": None}

    async def refresh(self, *, provider_id: str | None = None, reason: str = "manual") -> None:
        _ = reason
        selected = (provider_id,) if provider_id is not None else CODEBUDDY_PROVIDER_IDS
        async with self._lock:
            payload = self._load()
            providers = payload.setdefault("providers", {})
            for item in selected:
                provider = require_provider(item)
                previous = providers.get(provider.provider_id)
                try:
                    providers[provider.provider_id] = await self.refresh_provider(provider.provider_id)
                except (OSError, RuntimeError, ValueError) as exc:
                    if isinstance(previous, dict) and isinstance(previous.get("models"), list):
                        stale = dict(previous)
                        stale.update({"status": "stale_cache", "last_error": str(exc), "updated_at": _now()})
                        providers[provider.provider_id] = stale
                    else:
                        providers[provider.provider_id] = {"status": "error", "updated_at": _now(), "last_error": str(exc), "models": []}
            payload["engine"] = "codebuddy"
            self._save(payload)

    def get_snapshot(self) -> dict[str, Any]:
        payload = self._load()
        providers = payload.get("providers", {})
        all_models: list[dict[str, Any]] = []
        for provider_id in CODEBUDDY_PROVIDER_IDS:
            row = providers.get(provider_id) if isinstance(providers, dict) else None
            if isinstance(row, dict) and isinstance(row.get("models"), list):
                all_models.extend(model for model in row["models"] if isinstance(model, dict))
        return {"engine": "codebuddy", "source": "runtime_probe_cache", "providers": providers, "models": all_models}


codebuddy_model_catalog = CodeBuddyModelCatalog()
