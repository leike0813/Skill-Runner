from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from server.config import config
from server.engines.common.model_verbose_parser import extract_labeled_json_rows
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.engine_management.runtime_profile import RuntimeProfile, get_runtime_profile

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class KiloModelCatalog:
    def __init__(
        self,
        profile: RuntimeProfile | None = None,
        cli_manager: AgentCliManager | None = None,
    ) -> None:
        self.profile = profile or get_runtime_profile()
        self.cli_manager = cli_manager or AgentCliManager(self.profile)
        self._cache: dict[str, Any] = {}
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_guard: Callable[[], bool] | None = None
        self.scheduler = AsyncIOScheduler()
        self._job_added = False

    def _cache_path(self) -> Path:
        cache_dir = Path(config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR)
        template = str(config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_FILE_TEMPLATE)
        return cache_dir / template.format(engine="kilo")

    def cache_path(self) -> Path:
        return self._cache_path()

    def _seed_path(self) -> Path:
        profile = load_adapter_profile(
            "kilo",
            Path(config.SYSTEM.ROOT) / "server" / "engines" / "kilo" / "adapter" / "adapter_profile.json",
        )
        seed_path = profile.resolve_seed_path()
        if seed_path is None:
            return Path(config.SYSTEM.ROOT) / "server" / "engines" / "kilo" / "models" / "models_seed.json"
        return seed_path

    def _split_provider_model(self, value: str | None) -> tuple[str | None, str | None]:
        if not isinstance(value, str) or "/" not in value:
            return None, None
        provider, model = value.rsplit("/", 1)
        provider = provider.strip()
        model = model.strip()
        if not provider or not model:
            return None, None
        return provider, model

    def _normalize_models(self, rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            model_id_obj = row.get("id")
            if not isinstance(model_id_obj, str) or not model_id_obj.strip():
                continue
            model_id = model_id_obj.strip()
            if model_id in seen:
                continue
            seen.add(model_id)
            parsed_provider, parsed_model = self._split_provider_model(model_id)
            provider_obj = row.get("provider")
            provider = (
                parsed_provider
                or (provider_obj.strip() if isinstance(provider_obj, str) and provider_obj.strip() else None)
                or "kilo"
            )
            normalized.append(
                {
                    "id": model_id,
                    "provider": provider,
                    "provider_id": provider,
                    "model": parsed_model or model_id,
                    "display_name": row.get("display_name") or row.get("name") or model_id,
                    "deprecated": bool(row.get("deprecated", False)),
                    "notes": row.get("notes") or "runtime_probe_cache",
                    "supported_effort": row.get("supported_effort") or ["default"],
                }
            )
        return normalized

    def _derive_providers(self, models: list[dict[str, Any]]) -> list[str]:
        providers: list[str] = []
        for row in models:
            provider = row.get("provider")
            if isinstance(provider, str) and provider and provider not in providers:
                providers.append(provider)
        return sorted(providers)

    def _build_payload(
        self,
        *,
        models: list[dict[str, Any]],
        status: str,
        updated_at: str | None = None,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "engine": "kilo",
            "source": "runtime_probe_cache",
            "status": status,
            "updated_at": updated_at or _utc_now_iso(),
            "last_error": last_error,
            "providers": self._derive_providers(models),
            "models": models,
        }

    def _load_seed_payload(self, *, last_error: str | None = None) -> dict[str, Any]:
        path = self._seed_path()
        if not path.exists():
            return self._build_payload(models=[], status="seed_fallback", last_error=last_error)
        try:
            payload_obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            logger.warning("Failed to load kilo seed models from %s", path, exc_info=True)
            return self._build_payload(models=[], status="seed_fallback", last_error=last_error)
        if not isinstance(payload_obj, dict):
            return self._build_payload(models=[], status="seed_fallback", last_error=last_error)
        models = self._normalize_models(payload_obj.get("models"))
        status_obj = payload_obj.get("status")
        status = status_obj.strip() if isinstance(status_obj, str) and status_obj.strip() else "seed_fallback"
        updated_at_obj = payload_obj.get("updated_at")
        updated_at = updated_at_obj.strip() if isinstance(updated_at_obj, str) and updated_at_obj.strip() else None
        seed_error = last_error
        if seed_error is None:
            seed_error_obj = payload_obj.get("last_error")
            if isinstance(seed_error_obj, str) and seed_error_obj.strip():
                seed_error = seed_error_obj.strip()
        return self._build_payload(models=models, status=status, updated_at=updated_at, last_error=seed_error)

    def _write_cache(self, payload: dict[str, Any]) -> None:
        path = self._cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _read_cache(self) -> dict[str, Any] | None:
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            logger.warning("Failed to read kilo model cache: %s", path, exc_info=True)
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            return None
        return payload

    def start(self) -> None:
        cached = self._read_cache()
        if cached is not None:
            self._cache = cached
        elif not self._cache:
            self._cache = self._load_seed_payload(last_error=None)
            self._write_cache(self._cache)

        interval_minutes = int(config.SYSTEM.ENGINE_MODELS_CATALOG_REFRESH_INTERVAL_MINUTES)
        if interval_minutes > 0:
            if not self.scheduler.running:
                try:
                    if not self._job_added:
                        self.scheduler.add_job(self._scheduled_refresh, "interval", minutes=interval_minutes)
                        self._job_added = True
                    self.scheduler.start()
                except RuntimeError:
                    self.scheduler = AsyncIOScheduler()
                    self._job_added = False
                    self.scheduler.add_job(self._scheduled_refresh, "interval", minutes=interval_minutes)
                    self._job_added = True
                    self.scheduler.start()

    def set_refresh_guard(self, guard: Callable[[], bool]) -> None:
        self._refresh_guard = guard

    def _refresh_allowed(self) -> bool:
        return self._refresh_guard is None or self._refresh_guard()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _scheduled_refresh(self) -> None:
        if not self._refresh_allowed():
            return
        await self.refresh(reason="interval")

    def _resolve_probe_timeout_seconds(self) -> int:
        return max(1, int(config.SYSTEM.ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC))

    async def _run_models_probe(self, *, timeout_sec: int) -> list[dict[str, Any]]:
        command = self.cli_manager.resolve_engine_command("kilo")
        if command is None:
            raise RuntimeError("kilo CLI not found")
        env = self.profile.build_subprocess_env()
        stdout_text = await self._run_models_command(
            command,
            ["models", "--verbose"],
            env=env,
            timeout_sec=timeout_sec,
        )
        return self._parse_verbose_models(stdout_text)

    async def _run_models_command(
        self,
        command: Path,
        args: list[str],
        *,
        env: dict[str, str],
        timeout_sec: int,
    ) -> str:
        proc = await asyncio.create_subprocess_exec(
            str(command),
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_raw, stderr_raw = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"kilo models timed out after {timeout_sec}s") from exc
        stdout_text = (stdout_raw or b"").decode("utf-8", errors="replace")
        stderr_text = (stderr_raw or b"").decode("utf-8", errors="replace")
        if proc.returncode != 0:
            command_label = "kilo " + " ".join(args)
            raise RuntimeError(
                f"{command_label} exited with code {proc.returncode}: {(stderr_text or stdout_text).strip()}"
            )
        return stdout_text

    def _parse_plain_model_ids(self, stdout_text: str) -> list[str]:
        model_ids: list[str] = []
        seen: set[str] = set()
        for line in stdout_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("{") or stripped.startswith("["):
                continue
            candidate = stripped.split()[0].strip()
            if "/" not in candidate or candidate in seen:
                continue
            seen.add(candidate)
            model_ids.append(candidate)
        return model_ids

    def _supported_effort_from_variants(self, variants_obj: Any) -> list[str]:
        if not isinstance(variants_obj, dict):
            return ["default"]
        efforts: list[str] = []
        for key in variants_obj:
            if not isinstance(key, str):
                continue
            normalized = key.strip().lower()
            if normalized and normalized not in efforts:
                efforts.append(normalized)
        return efforts or ["default"]

    def _model_row_from_id(self, model_id: str, row: dict[str, Any] | None = None) -> dict[str, Any]:
        parsed_provider, parsed_model = self._split_provider_model(model_id)
        metadata = row or {}
        return {
            "id": model_id,
            "provider": parsed_provider or "kilo",
            "provider_id": parsed_provider or "kilo",
            "model": parsed_model or model_id,
            "display_name": metadata.get("display_name") or metadata.get("name") or model_id,
            "deprecated": bool(metadata.get("deprecated", False)),
            "notes": "runtime_probe_cache",
            "supported_effort": metadata.get("supported_effort")
            or self._supported_effort_from_variants(metadata.get("variants")),
        }

    def _parse_verbose_models(self, stdout_text: str) -> list[dict[str, Any]]:
        dedup: dict[str, dict[str, Any]] = {}
        labeled_rows = extract_labeled_json_rows(stdout_text, error_label="kilo models --verbose")
        for label, row in labeled_rows:
            row_id_obj = row.get("id")
            row_id = row_id_obj.strip() if isinstance(row_id_obj, str) and row_id_obj.strip() else ""
            canonical_id = label.strip() if isinstance(label, str) and label.strip() else row_id
            if not canonical_id or "/" not in canonical_id:
                continue
            dedup[canonical_id] = self._model_row_from_id(canonical_id, row)
        if not dedup:
            for candidate in self._parse_plain_model_ids(stdout_text):
                dedup[candidate] = self._model_row_from_id(candidate)
        if not dedup:
            raise RuntimeError("kilo models --verbose did not return parseable model data")
        return [dedup[key] for key in sorted(dedup.keys())]

    async def refresh(self, *, reason: str = "manual") -> None:
        if not self._refresh_allowed():
            return
        async with self._refresh_lock:
            _ = reason
            timeout_sec = self._resolve_probe_timeout_seconds()
            try:
                probed = await self._run_models_probe(timeout_sec=timeout_sec)
                if probed:
                    payload = self._build_payload(models=probed, status="ready", last_error=None)
                elif self._cache.get("models"):
                    payload = deepcopy(self._cache)
                    payload["status"] = "stale_cache"
                    payload["last_error"] = "kilo models returned empty output"
                else:
                    payload = self._load_seed_payload(last_error="kilo models returned empty output")
            except (OSError, RuntimeError, ValueError, TypeError) as exc:
                logger.warning("Failed to refresh kilo model catalog", exc_info=True)
                if self._cache.get("models"):
                    payload = deepcopy(self._cache)
                    payload["status"] = "stale_cache"
                    payload["last_error"] = str(exc)
                else:
                    payload = self._load_seed_payload(last_error=str(exc))
            payload["updated_at"] = _utc_now_iso()
            payload["providers"] = self._derive_providers(payload.get("models", []))
            self._cache = payload
            self._write_cache(payload)

    def request_refresh_async(self, *, reason: str) -> asyncio.Task[None] | None:
        _ = reason
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None
        if self._refresh_task and not self._refresh_task.done():
            return self._refresh_task
        self._refresh_task = loop.create_task(self.refresh(reason=reason))
        return self._refresh_task

    def get_snapshot(self) -> dict[str, Any]:
        if not self._cache:
            self._cache = self._load_seed_payload(last_error=None)
        return deepcopy(self._cache)


kilo_model_catalog = KiloModelCatalog()
