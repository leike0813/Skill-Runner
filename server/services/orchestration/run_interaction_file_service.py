from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException, UploadFile  # type: ignore[import-not-found]

from server.config import config
from server.models import (
    InteractionFileManifest,
    InteractionFileManifestEntry,
    InteractionFilePublicSummary,
    InteractionFileReplyMetadata,
    InteractionFileResponse,
    InteractionManagedFile,
    InteractionPublicFile,
    InteractionReplyRequest,
    InteractionReplyResponse,
    RunStatus,
)
from server.services.orchestration.run_interaction_service import (
    RunInteractionService,
    run_interaction_service,
)
from server.services.orchestration.run_store import run_store
from server.services.platform.async_compat import maybe_await
from server.runtime.protocol.schema_registry import (
    validate_interaction_file_continuation,
    validate_interaction_file_manifest,
    validate_interaction_file_metadata,
    validate_interaction_file_public_response,
)


PROTOCOL_MAX_FILES = 8
PROTOCOL_MAX_FILE_BYTES = 32 * 1024 * 1024
PROTOCOL_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_CHUNK_BYTES = 64 * 1024
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")
_SAFE_SUFFIX_RE = re.compile(r"^\.[A-Za-z0-9]{1,16}$")


@dataclass(frozen=True)
class InteractionFilePolicy:
    max_files: int
    max_file_bytes: int
    max_total_bytes: int


class InteractionFileReplyError(ValueError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _WrittenFile:
    file_index: int
    display_name: str
    storage_name: str
    size_bytes: int
    sha256: str


class RunInteractionFileService:
    def __init__(self, interaction_service: RunInteractionService) -> None:
        self._interaction_service = interaction_service

    def get_policy(self) -> InteractionFilePolicy:
        policy = InteractionFilePolicy(
            max_files=int(config.SYSTEM.INTERACTION_FILES.MAX_FILES),
            max_file_bytes=int(config.SYSTEM.INTERACTION_FILES.MAX_FILE_BYTES),
            max_total_bytes=int(config.SYSTEM.INTERACTION_FILES.MAX_TOTAL_BYTES),
        )
        maxima = InteractionFilePolicy(
            max_files=PROTOCOL_MAX_FILES,
            max_file_bytes=PROTOCOL_MAX_FILE_BYTES,
            max_total_bytes=PROTOCOL_MAX_TOTAL_BYTES,
        )
        for name in ("max_files", "max_file_bytes", "max_total_bytes"):
            value = getattr(policy, name)
            maximum = getattr(maxima, name)
            if value < 1 or value > maximum:
                raise RuntimeError(f"Invalid interaction file policy: {name}")
        return policy

    async def submit_files(
        self,
        *,
        request_id: str,
        metadata: InteractionFileReplyMetadata,
        uploads: list[UploadFile],
        background_tasks: BackgroundTasks,
        run_store_backend: Any = run_store,
    ) -> InteractionReplyResponse:
        policy = self.get_policy()
        validate_interaction_file_metadata(metadata.model_dump(mode="json", exclude_none=True))
        if not uploads:
            raise InteractionFileReplyError(422, "FILES_REQUIRED", "At least one file is required")
        if len(uploads) > policy.max_files:
            raise InteractionFileReplyError(413, "FILE_COUNT_LIMIT", "Too many files")

        try:
            _request_record, layout = await self._interaction_service.resolve_request_and_layout(
                request_id=request_id,
                run_store_backend=run_store_backend,
            )
        except HTTPException as exc:
            message = exc.detail if isinstance(exc.detail, str) else "Request is unavailable"
            raise InteractionFileReplyError(exc.status_code, "REQUEST_UNAVAILABLE", message) from exc

        record = await maybe_await(
            run_store_backend.get_interaction_reply_record(
                request_id,
                metadata.interaction_id,
            )
        )
        if not isinstance(record, dict):
            raise InteractionFileReplyError(409, "STALE_INTERACTION", "stale interaction")

        state = str(record.get("state") or "")
        existing_key = record.get("idempotency_key")
        is_replay_candidate = state != "pending" and existing_key == metadata.idempotency_key
        if state != "pending" and not is_replay_candidate:
            raise InteractionFileReplyError(409, "STALE_INTERACTION", "stale interaction")
        if state == "pending":
            pending_response = await self._interaction_service.get_pending(
                request_id=request_id,
                run_store_backend=run_store_backend,
            )
            if pending_response.status != RunStatus.WAITING_USER:
                raise InteractionFileReplyError(
                    409,
                    "RUN_NOT_WAITING_USER",
                    "Run is not waiting for user interaction",
                )
            if (
                pending_response.pending is None
                or pending_response.pending.interaction_id != metadata.interaction_id
            ):
                raise InteractionFileReplyError(409, "STALE_INTERACTION", "stale interaction")

        pending_payload = record.get("payload")
        if not isinstance(pending_payload, dict):
            raise InteractionFileReplyError(409, "STALE_INTERACTION", "stale interaction")
        self._validate_bindings(pending_payload, metadata, len(uploads))

        base_dir = layout.interaction_reply_files_dir
        temp_dir: Path | None = None
        final_dir: Path | None = None
        private_response: dict[str, Any] | None = None
        fingerprint = ""
        try:
            self._prepare_managed_root(layout.workspace_dir, base_dir)
            interaction_dir = base_dir / str(metadata.interaction_id)
            self._ensure_contained(base_dir, interaction_dir)
            interaction_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            receipt_token = uuid4().hex
            temp_dir = interaction_dir / f".tmp-{receipt_token}"
            final_dir = interaction_dir / receipt_token
            temp_dir.mkdir(mode=0o700, exist_ok=False)

            written = await self._stream_uploads(
                uploads=uploads,
                temp_dir=temp_dir,
                policy=policy,
            )
            fingerprint = self._fingerprint(metadata, written)

            if is_replay_candidate:
                stored_fingerprint = record.get("fingerprint")
                if stored_fingerprint != fingerprint:
                    raise InteractionFileReplyError(
                        409,
                        "IDEMPOTENCY_CONFLICT",
                        "idempotency_key already used with different files",
                    )
                receipt = record.get("receipt")
                if not isinstance(receipt, dict):
                    raise InteractionFileReplyError(
                        409,
                        "IDEMPOTENCY_RECEIPT_MISSING",
                        "Stored interaction receipt is unavailable",
                    )
                return InteractionReplyResponse.model_validate(receipt)

            private_model, public_model, manifest = self._build_payloads(
                request_id=request_id,
                metadata=metadata,
                written=written,
                workspace_dir=layout.workspace_dir,
                final_dir=final_dir,
                receipt_token=receipt_token,
                fingerprint=fingerprint,
            )
            private_response = private_model.model_dump(mode="json", exclude_none=True)
            public_response = public_model.model_dump(mode="json", exclude_none=True)
            manifest_payload = manifest.model_dump(mode="json", exclude_none=True)
            validate_interaction_file_continuation(private_response)
            validate_interaction_file_public_response(public_response)
            validate_interaction_file_manifest(manifest_payload)
            (temp_dir / "manifest.json").write_text(
                json.dumps(manifest_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_dir, final_dir)
            temp_dir = None

            result = await self._interaction_service.submit_reply(
                request_id=request_id,
                request=InteractionReplyRequest(
                    mode="interaction",
                    interaction_id=metadata.interaction_id,
                    response=private_response,
                    idempotency_key=metadata.idempotency_key,
                ),
                background_tasks=background_tasks,
                run_store_backend=run_store_backend,
                idempotency_fingerprint=fingerprint,
                observability_response=public_response,
            )
            winning_record = await maybe_await(
                run_store_backend.get_interaction_reply_record(
                    request_id,
                    metadata.interaction_id,
                    metadata.idempotency_key,
                )
            )
            if (
                final_dir is not None
                and isinstance(winning_record, dict)
                and winning_record.get("response") != private_response
            ):
                self._remove_tree(final_dir)
                final_dir = None
            return result
        except InteractionFileReplyError:
            raise
        except HTTPException as exc:
            raise InteractionFileReplyError(
                exc.status_code,
                "INTERACTION_REPLY_REJECTED",
                exc.detail if isinstance(exc.detail, str) else "Interaction reply was rejected",
            ) from exc
        except (OSError, ValueError, TypeError) as exc:
            raise InteractionFileReplyError(
                500,
                "INTERACTION_FILE_STORAGE_FAILED",
                "Interaction file storage failed",
            ) from exc
        finally:
            if temp_dir is not None:
                self._remove_tree(temp_dir)
            if final_dir is not None and private_response is not None:
                stored = await maybe_await(
                    run_store_backend.get_interaction_reply_record(
                        request_id,
                        metadata.interaction_id,
                        metadata.idempotency_key,
                    )
                )
                if not isinstance(stored, dict) or stored.get("response") != private_response:
                    self._remove_tree(final_dir)

    def _validate_bindings(
        self,
        pending: dict[str, Any],
        metadata: InteractionFileReplyMetadata,
        file_count: int,
    ) -> None:
        if pending.get("kind") != "upload_files":
            raise InteractionFileReplyError(
                409,
                "INTERACTION_KIND_MISMATCH",
                "Pending interaction does not accept files",
            )
        ui_hints = pending.get("ui_hints")
        if not isinstance(ui_hints, dict) or ui_hints.get("kind") != "upload_files":
            raise InteractionFileReplyError(
                409,
                "INTERACTION_HINT_MISMATCH",
                "Pending interaction does not declare file upload hints",
            )
        declared_items = ui_hints.get("files")
        if not isinstance(declared_items, list) or not declared_items:
            raise InteractionFileReplyError(422, "FILE_SLOTS_MISSING", "No file slots are declared")
        declared: dict[str, bool] = {}
        for item in declared_items:
            if not isinstance(item, dict):
                raise InteractionFileReplyError(422, "INVALID_FILE_SLOT", "Invalid file slot")
            name = str(item.get("name") or "").strip()
            if not name or name in declared:
                raise InteractionFileReplyError(422, "INVALID_FILE_SLOT", "Invalid file slot")
            declared[name] = bool(item.get("required", False))

        slots: set[str] = set()
        indices: set[int] = set()
        for binding in metadata.bindings:
            slot = binding.slot.strip()
            if slot not in declared:
                raise InteractionFileReplyError(422, "UNKNOWN_FILE_SLOT", "Unknown file slot")
            if slot in slots:
                raise InteractionFileReplyError(422, "DUPLICATE_FILE_SLOT", "Duplicate file slot")
            if binding.file_index >= file_count:
                raise InteractionFileReplyError(422, "FILE_INDEX_OUT_OF_RANGE", "File index is out of range")
            if binding.file_index in indices:
                raise InteractionFileReplyError(422, "DUPLICATE_FILE_INDEX", "Duplicate file index")
            slots.add(slot)
            indices.add(binding.file_index)
        if indices != set(range(file_count)):
            raise InteractionFileReplyError(422, "UNBOUND_FILE", "Every file must be bound exactly once")
        missing = {slot for slot, required in declared.items() if required and slot not in slots}
        if missing:
            raise InteractionFileReplyError(422, "REQUIRED_FILE_SLOT_MISSING", "Required file slot is missing")

    async def _stream_uploads(
        self,
        *,
        uploads: list[UploadFile],
        temp_dir: Path,
        policy: InteractionFilePolicy,
    ) -> list[_WrittenFile]:
        total_bytes = 0
        written: list[_WrittenFile] = []
        for file_index, upload in enumerate(uploads):
            display_name = self._display_name(upload.filename)
            suffix = Path(display_name).suffix
            safe_suffix = suffix.lower() if _SAFE_SUFFIX_RE.fullmatch(suffix) else ""
            storage_name = f"{file_index:02d}-{uuid4().hex}{safe_suffix}"
            target = temp_dir / storage_name
            digest = hashlib.sha256()
            file_bytes = 0
            with target.open("xb") as handle:
                while True:
                    chunk = await upload.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    file_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if file_bytes > policy.max_file_bytes:
                        raise InteractionFileReplyError(413, "FILE_SIZE_LIMIT", "File is too large")
                    if total_bytes > policy.max_total_bytes:
                        raise InteractionFileReplyError(413, "TOTAL_SIZE_LIMIT", "Upload is too large")
                    digest.update(chunk)
                    handle.write(chunk)
            if file_bytes == 0:
                raise InteractionFileReplyError(422, "EMPTY_FILE", "Empty files are not accepted")
            written.append(
                _WrittenFile(
                    file_index=file_index,
                    display_name=display_name,
                    storage_name=storage_name,
                    size_bytes=file_bytes,
                    sha256=digest.hexdigest(),
                )
            )
        return written

    def _build_payloads(
        self,
        *,
        request_id: str,
        metadata: InteractionFileReplyMetadata,
        written: list[_WrittenFile],
        workspace_dir: Path,
        final_dir: Path,
        receipt_token: str,
        fingerprint: str,
    ) -> tuple[InteractionFileResponse, InteractionFilePublicSummary, InteractionFileManifest]:
        by_index = {item.file_index: item for item in written}
        managed: list[InteractionManagedFile] = []
        public: list[InteractionPublicFile] = []
        manifest_entries: list[InteractionFileManifestEntry] = []
        for binding in metadata.bindings:
            item = by_index[binding.file_index]
            path = (final_dir / item.storage_name).relative_to(workspace_dir).as_posix()
            managed.append(
                InteractionManagedFile(
                    slot=binding.slot.strip(),
                    name=item.display_name,
                    path=path,
                    size_bytes=item.size_bytes,
                )
            )
            public.append(
                InteractionPublicFile(
                    slot=binding.slot.strip(),
                    name=item.display_name,
                    size_bytes=item.size_bytes,
                )
            )
            manifest_entries.append(
                InteractionFileManifestEntry(
                    slot=binding.slot.strip(),
                    name=item.display_name,
                    path=path,
                    size_bytes=item.size_bytes,
                    sha256=item.sha256,
                )
            )
        return (
            InteractionFileResponse(message=metadata.message, files=managed),
            InteractionFilePublicSummary(message=metadata.message, files=public),
            InteractionFileManifest(
                request_id=request_id,
                interaction_id=metadata.interaction_id,
                idempotency_key=metadata.idempotency_key,
                receipt_token=receipt_token,
                fingerprint=fingerprint,
                files=manifest_entries,
            ),
        )

    def _fingerprint(
        self,
        metadata: InteractionFileReplyMetadata,
        written: list[_WrittenFile],
    ) -> str:
        by_index = {item.file_index: item for item in written}
        payload = {
            "interaction_id": metadata.interaction_id,
            "idempotency_key": metadata.idempotency_key,
            "message": metadata.message,
            "bindings": [
                {
                    "slot": binding.slot.strip(),
                    "file_index": binding.file_index,
                    "name": by_index[binding.file_index].display_name,
                    "size_bytes": by_index[binding.file_index].size_bytes,
                    "sha256": by_index[binding.file_index].sha256,
                }
                for binding in metadata.bindings
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _display_name(self, raw_name: str | None) -> str:
        normalized = str(raw_name or "").replace("\\", "/").split("/")[-1]
        normalized = _CONTROL_CHARS_RE.sub("", normalized).strip()
        if not normalized or normalized in {".", ".."}:
            raise InteractionFileReplyError(422, "INVALID_FILENAME", "File name is invalid")
        return normalized

    def _prepare_managed_root(self, workspace_dir: Path, base_dir: Path) -> None:
        workspace = workspace_dir.resolve(strict=True)
        current = workspace
        relative = base_dir.relative_to(workspace_dir)
        for part in relative.parts:
            current = current / part
            if current.exists() and (current.is_symlink() or not current.is_dir()):
                raise InteractionFileReplyError(
                    422,
                    "MANAGED_PATH_CONFLICT",
                    "Managed upload path is unavailable",
                )
        base_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._ensure_contained(workspace, base_dir)

    def _ensure_contained(self, parent: Path, child: Path) -> None:
        try:
            child.resolve(strict=False).relative_to(parent.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise InteractionFileReplyError(
                422,
                "MANAGED_PATH_ESCAPE",
                "Managed upload path is invalid",
            ) from exc

    def _remove_tree(self, path: Path) -> None:
        if path.exists() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)


run_interaction_file_service = RunInteractionFileService(run_interaction_service)


__all__ = [
    "InteractionFilePolicy",
    "InteractionFileReplyError",
    "RunInteractionFileService",
    "run_interaction_file_service",
]
