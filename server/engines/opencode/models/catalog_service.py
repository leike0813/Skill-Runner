import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from server.config import config
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.engine_management.runtime_profile import RuntimeProfile, get_runtime_profile

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OpencodeModelCatalog:
    def __init__(
        self,
        profile: RuntimeProfile | None = None,
        cli_manager: AgentCliManager | None = None,
    ) -> None:
        self.profile = profile or get_runtime_profile()
        self.cli_manager = cli_manager or AgentCliManager(self.profile)
        self._cache: Dict[str, Any] = {}
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None
        self.scheduler = AsyncIOScheduler()
        self._job_added = False

    def _cache_path(self) -> Path:
        cache_dir = Path(config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR)
        template = str(config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_FILE_TEMPLATE)
        return cache_dir / template.format(engine="opencode")

    def cache_path(self) -> Path:
        return self._cache_path()

    def _seed_path(self) -> Path:
        profile = load_adapter_profile(
            "opencode",
            Path(config.SYSTEM.ROOT) / "server" / "engines" / "opencode" / "adapter" / "adapter_profile.json",
        )
        seed_path = profile.resolve_seed_path()
        if seed_path is None:
            return Path(config.SYSTEM.ROOT) / "server" / "engines" / "opencode" / "models" / "models_seed.json"
        return seed_path

    def _normalize_models(self, rows: Any) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            model_id = row.get("id")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            model_id = model_id.strip()
            parsed_provider, parsed_model = self._split_provider_model(model_id)
            provider_obj = row.get("provider")
            model_obj = row.get("model")
            provider = provider_obj.strip() if isinstance(provider_obj, str) and provider_obj.strip() else parsed_provider
            model = model_obj.strip() if isinstance(model_obj, str) and model_obj.strip() else parsed_model
            if not provider or not model:
                continue
            normalized.append(
                {
                    "id": model_id,
                    "provider": provider,
                    "model": model,
                    "display_name": row.get("display_name"),
                    "deprecated": bool(row.get("deprecated", False)),
                    "notes": row.get("notes"),
                    "supported_effort": row.get("supported_effort"),
                }
            )
        return normalized

    def _load_seed_payload(self, *, last_error: str | None = None) -> Dict[str, Any]:
        path = self._seed_path()
        seed_fallback_error = last_error
        if not path.exists():
            return self._build_payload(models=[], status="seed_fallback", last_error=seed_fallback_error)
        try:
            payload_obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            logger.warning("Failed to load opencode seed models from %s", path, exc_info=True)
            return self._build_payload(models=[], status="seed_fallback", last_error=seed_fallback_error)

        if not isinstance(payload_obj, dict):
            return self._build_payload(models=[], status="seed_fallback", last_error=seed_fallback_error)

        models = self._normalize_models(payload_obj.get("models"))
        status_obj = payload_obj.get("status")
        status = status_obj.strip() if isinstance(status_obj, str) and status_obj.strip() else "seed_fallback"
        updated_at_obj = payload_obj.get("updated_at")
        updated_at = updated_at_obj.strip() if isinstance(updated_at_obj, str) and updated_at_obj.strip() else None
        if seed_fallback_error is None:
            seed_error_obj = payload_obj.get("last_error")
            if isinstance(seed_error_obj, str) and seed_error_obj.strip():
                seed_fallback_error = seed_error_obj.strip()

        return self._build_payload(
            models=models,
            status=status,
            updated_at=updated_at,
            last_error=seed_fallback_error,
        )

    def _split_provider_model(self, value: str | None) -> tuple[str | None, str | None]:
        if not isinstance(value, str) or "/" not in value:
            return None, None
        provider, model = value.split("/", 1)
        provider = provider.strip()
        model = model.strip()
        if not provider or not model:
            return None, None
        return provider, model

    def _derive_providers(self, models: List[Dict[str, Any]]) -> List[str]:
        providers = []
        for row in models:
            provider = row.get("provider")
            if isinstance(provider, str) and provider and provider not in providers:
                providers.append(provider)
        return sorted(providers)

    def _build_payload(
        self,
        *,
        models: List[Dict[str, Any]],
        status: str,
        updated_at: str | None = None,
        last_error: str | None = None,
    ) -> Dict[str, Any]:
        return {
            "engine": "opencode",
            "source": "runtime_probe_cache",
            "status": status,
            "updated_at": updated_at or _utc_now_iso(),
            "last_error": last_error,
            "providers": self._derive_providers(models),
            "models": models,
        }

    def _write_cache(self, payload: Dict[str, Any]) -> None:
        path = self._cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _read_cache(self) -> Dict[str, Any] | None:
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            logger.warning("Failed to read opencode model cache: %s", path, exc_info=True)
            return None
        if not isinstance(payload, dict):
            return None
        rows = payload.get("models")
        if not isinstance(rows, list):
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

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _scheduled_refresh(self) -> None:
        await self.refresh(reason="interval")

    def _resolve_probe_timeout_seconds(self) -> int:
        return max(1, int(config.SYSTEM.ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC))

    async def _run_models_probe(self, *, timeout_sec: int) -> List[Dict[str, Any]]:
        command = self.cli_manager.resolve_engine_command("opencode")
        if command is None:
            raise RuntimeError("opencode CLI not found")

        env = self.profile.build_subprocess_env()
        proc = await asyncio.create_subprocess_exec(
            str(command),
            "models",
            "--verbose",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_raw, stderr_raw = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"opencode models timed out after {timeout_sec}s") from exc

        stdout_text = (stdout_raw or b"").decode("utf-8", errors="replace")
        stderr_text = (stderr_raw or b"").decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(
                f"opencode models exited with code {proc.returncode}: {(stderr_text or stdout_text).strip()}"
            )
        return self._parse_verbose_models(stdout_text)

    def _extract_verbose_rows(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            models_obj = payload.get("models")
            if isinstance(models_obj, list):
                return [item for item in models_obj if isinstance(item, dict)]
        return []

    def _extract_verbose_labeled_rows(self, stdout_text: str) -> List[tuple[str | None, Dict[str, Any]]]:
        try:
            payload = json.loads(stdout_text)
        except json.JSONDecodeError:
            return self._extract_verbose_block_rows(stdout_text)
        return [(None, row) for row in self._extract_verbose_rows(payload)]

    def _extract_verbose_block_rows(self, stdout_text: str) -> List[tuple[str | None, Dict[str, Any]]]:
        decoder = json.JSONDecoder()
        rows: List[tuple[str | None, Dict[str, Any]]] = []
        position = 0
        text = stdout_text
        text_len = len(text)
        while position < text_len:
            while position < text_len and text[position].isspace():
                position += 1
            if position >= text_len:
                break
            label: str | None = None
            if text[position] != "{":
                line_end = text.find("\n", position)
                if line_end == -1:
                    break
                candidate = text[position:line_end].strip()
                position = line_end + 1
                if candidate:
                    label = candidate
                while position < text_len and text[position].isspace():
                    position += 1
            if position >= text_len or text[position] != "{":
                continue
            try:
                payload, next_position = decoder.raw_decode(text, position)
            except json.JSONDecodeError as exc:
                raise RuntimeError("opencode models --verbose returned malformed object blocks") from exc
            if isinstance(payload, dict):
                rows.append((label, payload))
            position = next_position
        return rows

    def _supported_effort_from_variants(self, variants_obj: Any) -> List[str]:
        if not isinstance(variants_obj, dict):
            return ["default"]
        efforts: List[str] = []
        for key in variants_obj.keys():
            if not isinstance(key, str):
                continue
            normalized = key.strip().lower()
            if normalized and normalized not in efforts:
                efforts.append(normalized)
        return efforts or ["default"]

    def _parse_verbose_models(self, stdout_text: str) -> List[Dict[str, Any]]:
        dedup: Dict[str, Dict[str, Any]] = {}
        labeled_rows = self._extract_verbose_labeled_rows(stdout_text)
        if not labeled_rows:
            raise RuntimeError("opencode models --verbose did not return parseable model data")
        for label, row in labeled_rows:
            row_id_obj = row.get("id")
            short_id = row_id_obj.strip() if isinstance(row_id_obj, str) and row_id_obj.strip() else ""
            provider_obj = row.get("provider")
            provider = provider_obj.strip() if isinstance(provider_obj, str) and provider_obj.strip() else None
            provider_id_obj = row.get("providerID")
            if provider is None and isinstance(provider_id_obj, str) and provider_id_obj.strip():
                provider = provider_id_obj.strip()
            model_obj = row.get("model")
            model = model_obj.strip() if isinstance(model_obj, str) and model_obj.strip() else None
            parsed_provider, parsed_model = self._split_provider_model(label)
            if parsed_model is None:
                parsed_provider, parsed_model = self._split_provider_model(short_id)
            provider = provider or parsed_provider
            model = model or parsed_model or short_id
            if not provider or not model:
                continue
            canonical_id = label.strip() if isinstance(label, str) and label.strip() else f"{provider}/{model}"
            dedup[canonical_id] = {
                "id": canonical_id,
                "provider": provider,
                "provider_id": provider,
                "model": model,
                "display_name": row.get("name") or row.get("display_name"),
                "deprecated": bool(row.get("deprecated", False)),
                "notes": "runtime_probe_cache",
                "supported_effort": self._supported_effort_from_variants(row.get("variants")),
            }
        return [dedup[key] for key in sorted(dedup.keys())]

    async def refresh(self, *, reason: str = "manual") -> None:
        async with self._refresh_lock:
            timeout_sec = self._resolve_probe_timeout_seconds()
            try:
                probed = await self._run_models_probe(timeout_sec=timeout_sec)
                if probed:
                    payload = self._build_payload(models=probed, status="ready", last_error=None)
                elif self._cache.get("models"):
                    payload = deepcopy(self._cache)
                    payload["status"] = "stale_cache"
                    payload["last_error"] = "opencode models returned empty output"
                else:
                    payload = self._load_seed_payload(
                        last_error="opencode models returned empty output",
                    )
            except (OSError, RuntimeError, ValueError, TypeError) as exc:
                logger.warning("Failed to refresh opencode model catalog", exc_info=True)
                if "opencode CLI not found" in str(exc):
                    report_path = Path(config.SYSTEM.DATA_DIR) / "agent_bootstrap_report.json"
                    logger.warning(
                        "Opencode model probe missing CLI. Check bootstrap diagnostics report=%s and engine status cache table in runs.db=%s",
                        report_path,
                        config.SYSTEM.RUNS_DB,
                    )
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

    def get_snapshot(self) -> Dict[str, Any]:
        if not self._cache:
            self._cache = self._load_seed_payload(last_error=None)
        return deepcopy(self._cache)


opencode_model_catalog = OpencodeModelCatalog()
