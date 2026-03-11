from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml  # type: ignore[import-untyped]

from server.config import config
from server.models import (
    EngineInteractiveProfile,
    InteractiveErrorCode,
    InteractiveResolutionMode,
    OrchestratorEventType,
    PendingOwner,
    ResumeCause,
    RunStatus,
)
from server.runtime.common.ask_user_text import (
    DEFAULT_INTERACTION_PROMPT,
    contains_ask_user_yaml_block,
    normalize_interaction_text,
    strip_ask_user_yaml_blocks,
)
from server.runtime.protocol.factories import make_resume_command
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_pending_interaction,
    validate_resume_command,
)
from server.runtime.session.statechart import (
    timeout_requires_auto_decision,
    waiting_reply_target_status,
)
from server.services.platform.async_compat import maybe_await
from server.services.orchestration.run_projection_service import run_projection_service

logger = logging.getLogger(__name__)


class RunInteractionLifecycleService:
    async def inject_interactive_resume_context(
        self,
        *,
        request_id: str,
        profile: EngineInteractiveProfile,
        options: dict[str, Any],
        run_dir: Path,
        run_store_backend: Any,
        append_internal_schema_warning: Callable[..., None],
        resolve_attempt_number: Callable[..., Awaitable[int]],
        build_reply_prompt: Callable[[Any], str],
    ) -> None:
        if "__interactive_reply_payload" not in options:
            return
        interaction_id_raw = options.get("__interactive_reply_interaction_id", 0)
        try:
            interaction_id = int(interaction_id_raw)
        except (TypeError, ValueError):
            interaction_id = 0
        resolution_mode_raw = options.get(
            "__interactive_resolution_mode",
            InteractiveResolutionMode.USER_REPLY.value,
        )
        resolution_mode = (
            str(resolution_mode_raw).strip()
            if resolution_mode_raw
            else InteractiveResolutionMode.USER_REPLY.value
        )
        resume_command = make_resume_command(
            interaction_id=max(1, interaction_id),
            response=options.get("__interactive_reply_payload"),
            resolution_mode=resolution_mode,
            auto_decide_reason=(
                str(options.get("__interactive_auto_reason"))
                if isinstance(options.get("__interactive_auto_reason"), str)
                else None
            ),
            auto_decide_policy=(
                str(options.get("__interactive_auto_policy"))
                if isinstance(options.get("__interactive_auto_policy"), str)
                else None
            ),
        )
        try:
            validate_resume_command(resume_command)
        except ProtocolSchemaViolation as exc:
            append_internal_schema_warning(
                run_dir=run_dir,
                attempt_number=await resolve_attempt_number(request_id=request_id, is_interactive=True),
                schema_path="interactive_resume_command",
                detail=str(exc),
            )
            resume_command = make_resume_command(
                interaction_id=max(1, interaction_id),
                response=options.get("__interactive_reply_payload"),
                resolution_mode=InteractiveResolutionMode.USER_REPLY.value,
            )
        if interaction_id > 0:
            await maybe_await(run_store_backend.append_interaction_history(
                request_id=request_id,
                interaction_id=interaction_id,
                event_type="reply",
                payload={
                    "response": resume_command["response"],
                    "source_attempt": int(options.get("__interactive_source_attempt") or 1),
                    "resolution_mode": resume_command["resolution_mode"],
                    "resolved_at": datetime.utcnow().isoformat(),
                    "auto_decide_reason": resume_command.get("auto_decide_reason"),
                    "auto_decide_policy": resume_command.get("auto_decide_policy"),
                },
                source_attempt=int(options.get("__interactive_source_attempt") or 1),
            ))
            await maybe_await(run_store_backend.consume_interaction_reply(request_id, interaction_id))
        options["__prompt_override"] = build_reply_prompt(resume_command.get("response"))
        handle = await maybe_await(run_store_backend.get_engine_session_handle(request_id))
        if not handle:
            raise RuntimeError(
                f"{InteractiveErrorCode.SESSION_RESUME_FAILED.value}: missing session handle"
            )
        options["__resume_session_handle"] = handle
        await self.write_interaction_mirror_files(
            run_dir=run_dir,
            request_id=request_id,
            pending_interaction=(await maybe_await(run_store_backend.get_pending_interaction(request_id))) or {
                "interaction_id": interaction_id,
                "kind": "open_text",
                "prompt": "",
                "options": [],
                "ui_hints": {},
                "default_decision_policy": "engine_judgement",
                "required_fields": [],
            },
            run_store_backend=run_store_backend,
        )

    def extract_pending_interaction(
        self,
        payload: dict[str, Any],
        *,
        fallback_interaction_id: int | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        interaction_payload: dict[str, Any] | None = None
        if isinstance(payload.get("ask_user"), dict):
            interaction_payload = payload.get("ask_user")
        elif payload.get("action") == "ask_user" and isinstance(payload.get("interaction"), dict):
            interaction_payload = payload.get("interaction")
        elif payload.get("type") == "ask_user" and isinstance(payload.get("interaction"), dict):
            interaction_payload = payload.get("interaction")
        elif self.looks_like_direct_interaction_payload(payload):
            interaction_payload = payload
        if interaction_payload is None:
            return None

        ui_hints_raw = interaction_payload.get("ui_hints")
        ui_hints = ui_hints_raw if isinstance(ui_hints_raw, dict) else {}
        hint_obj = interaction_payload.get("hint")
        if not (isinstance(hint_obj, str) and hint_obj.strip()):
            hint_obj = ui_hints.get("hint")
        hint_text = (
            self.normalize_interaction_prompt(hint_obj)
            if isinstance(hint_obj, str) and hint_obj.strip()
            else ""
        )
        if hint_text:
            ui_hints = {**ui_hints, "hint": hint_text}
        prompt_obj = interaction_payload.get("prompt") or interaction_payload.get("question")
        prompt = (
            self.normalize_interaction_prompt(prompt_obj)
            if isinstance(prompt_obj, str) and prompt_obj.strip()
            else ""
        )
        if not prompt:
            prompt = DEFAULT_INTERACTION_PROMPT
        interaction_id = 0
        interaction_id_source = "payload"
        interaction_id_raw = interaction_payload.get("interaction_id")
        raw_interaction_id: str | None = None
        if interaction_id_raw is not None:
            try:
                interaction_id = int(interaction_id_raw)
            except (TypeError, ValueError):
                interaction_id = 0
                raw_interaction_id = str(interaction_id_raw).strip() or None
        if interaction_id <= 0 and fallback_interaction_id is not None and int(fallback_interaction_id) > 0:
            interaction_id = int(fallback_interaction_id)
            interaction_id_source = "fallback"
        if interaction_id <= 0:
            return None
        kind = self.normalize_interaction_kind_name(interaction_payload.get("kind"))
        options_payload = interaction_payload.get("options", [])
        options_normalized: list[dict[str, Any]] = []
        if isinstance(options_payload, list):
            for item in options_payload:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if not isinstance(label, str) or not label.strip():
                    continue
                options_normalized.append({"label": label, "value": item.get("value")})
        required_fields = interaction_payload.get("required_fields")
        if not isinstance(required_fields, list):
            required_fields = []
        default_decision_policy_raw = interaction_payload.get("default_decision_policy")
        default_decision_policy = (
            default_decision_policy_raw.strip()
            if isinstance(default_decision_policy_raw, str) and default_decision_policy_raw.strip()
            else "engine_judgement"
        )
        context_obj = interaction_payload.get("context")
        context: dict[str, Any] | None
        if isinstance(context_obj, dict):
            context = dict(context_obj)
        else:
            context = {}
        if raw_interaction_id:
            context["external_interaction_id"] = raw_interaction_id
        if interaction_id_source != "payload":
            context["interaction_id_source"] = interaction_id_source
        if not context:
            context = None
        return {
            "interaction_id": interaction_id,
            "kind": kind,
            "prompt": prompt,
            "options": options_normalized,
            "ui_hints": ui_hints,
            "default_decision_policy": default_decision_policy,
            "required_fields": required_fields,
            "context": context,
        }

    def infer_pending_interaction(
        self,
        payload: dict[str, Any],
        *,
        fallback_interaction_id: int,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        outcome_obj = payload.get("outcome")
        if isinstance(outcome_obj, str) and outcome_obj.strip().lower() == "error":
            return None
        extracted = self.extract_pending_interaction(
            payload,
            fallback_interaction_id=fallback_interaction_id,
        )
        if extracted is not None:
            return extracted
        if fallback_interaction_id <= 0:
            return None
        return {
            "interaction_id": int(fallback_interaction_id),
            "kind": "open_text",
            "prompt": DEFAULT_INTERACTION_PROMPT,
            "options": [],
            "ui_hints": {},
            "default_decision_policy": "engine_judgement",
            "required_fields": [],
            "context": {"inferred_from": "done_marker_missing"},
        }

    def infer_pending_interaction_from_runtime_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
        fallback_interaction_id: int,
    ) -> dict[str, Any] | None:
        if fallback_interaction_id <= 0:
            return None
        try:
            parsed = adapter.parse_runtime_stream(
                stdout_raw=(raw_stdout or "").encode("utf-8", errors="replace"),
                stderr_raw=(raw_stderr or "").encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
        except Exception as exc:
            # Third-party parser boundary: treat parse failure as "no interaction inferred".
            logger.warning(
                "interactive lifecycle runtime stream parse failed",
                extra={
                    "component": "orchestration.run_interaction_lifecycle_service",
                    "action": "infer_pending_interaction_from_runtime_stream.parse_runtime_stream",
                    "error_type": type(exc).__name__,
                    "fallback": "skip_runtime_stream_interaction_inference",
                },
                exc_info=True,
            )
            return None
        messages = parsed.get("assistant_messages") if isinstance(parsed, dict) else None
        if not isinstance(messages, list) or not messages:
            return None
        has_message = False
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            text_obj = item.get("text")
            if isinstance(text_obj, str) and text_obj.strip():
                has_message = True
                break
        if not has_message:
            return None
        return {
            "interaction_id": int(fallback_interaction_id),
            "kind": "open_text",
            "prompt": DEFAULT_INTERACTION_PROMPT,
            "options": [],
            "ui_hints": {},
            "default_decision_policy": "engine_judgement",
            "required_fields": [],
            "context": {"inferred_from": "runtime_stream_assistant_message"},
        }

    def contains_ask_user_signal_in_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
    ) -> bool:
        try:
            parsed = adapter.parse_runtime_stream(
                stdout_raw=(raw_stdout or "").encode("utf-8", errors="replace"),
                stderr_raw=(raw_stderr or "").encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
            messages = parsed.get("assistant_messages") if isinstance(parsed, dict) else None
            if isinstance(messages, list):
                for item in reversed(messages):
                    if not isinstance(item, dict):
                        continue
                    text_obj = item.get("text")
                    if contains_ask_user_yaml_block(text_obj):
                        return True
        except Exception as exc:
            logger.warning(
                "interactive lifecycle ask_user signal probe parse failed",
                extra={
                    "component": "orchestration.run_interaction_lifecycle_service",
                    "action": "contains_ask_user_signal_in_stream.parse_runtime_stream",
                    "error_type": type(exc).__name__,
                    "fallback": "scan_raw_stdout_stderr",
                },
                exc_info=True,
            )

        stream_text = "\n".join(part for part in [raw_stdout or "", raw_stderr or ""] if isinstance(part, str))
        return contains_ask_user_yaml_block(stream_text)

    def strip_prompt_yaml_blocks(self, text: str) -> str:
        return strip_ask_user_yaml_blocks(text)

    def normalize_interaction_prompt(self, raw_prompt: Any) -> str:
        return normalize_interaction_text(raw_prompt)

    def normalize_interaction_kind_name(self, raw_kind: Any) -> str:
        kind_name = str(raw_kind or "").strip().lower()
        alias_map = {
            "decision": "choose_one",
            "confirmation": "confirm",
            "clarification": "open_text",
            "single_select": "choose_one",
        }
        kind_name = alias_map.get(kind_name, kind_name)
        allowed = {"choose_one", "confirm", "fill_fields", "open_text", "risk_ack"}
        if kind_name not in allowed:
            return "open_text"
        return kind_name

    def looks_like_direct_interaction_payload(self, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        if (
            "interaction_id" in payload
            and (
                "kind" in payload
                or isinstance(payload.get("options"), list)
                or isinstance(payload.get("ui_hints"), dict)
            )
        ):
            return True
        prompt_obj = payload.get("prompt") or payload.get("question")
        ui_hints_obj = payload.get("ui_hints")
        hint_obj = payload.get("hint")
        if not (isinstance(hint_obj, str) and hint_obj.strip()):
            hint_obj = ui_hints_obj.get("hint") if isinstance(ui_hints_obj, dict) else None
        has_prompt = isinstance(prompt_obj, str) and bool(prompt_obj.strip())
        has_hint = isinstance(hint_obj, str) and bool(hint_obj.strip())
        if not has_prompt and not has_hint:
            return False
        if "interaction_id" in payload:
            return True
        if "kind" in payload:
            return True
        if isinstance(payload.get("options"), list):
            return True
        return False

    def extract_pending_interaction_from_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
        fallback_interaction_id: int | None,
    ) -> dict[str, Any] | None:
        def _extract_from_text(text: str) -> dict[str, Any] | None:
            if not text.strip():
                return None
            snippets: list[str] = []
            tag_pattern = re.compile(
                r"<ASK_USER_YAML>\s*(.*?)\s*</ASK_USER_YAML>",
                re.IGNORECASE | re.DOTALL,
            )
            snippets.extend(match.group(1) for match in tag_pattern.finditer(text))
            fence_pattern = re.compile(
                r"```(?:ask_user_yaml|ask-user-yaml)\s*(.*?)```",
                re.IGNORECASE | re.DOTALL,
            )
            snippets.extend(match.group(1) for match in fence_pattern.finditer(text))
            for snippet in snippets:
                try:
                    parsed = yaml.safe_load(snippet)
                except yaml.YAMLError:
                    continue
                if not isinstance(parsed, dict):
                    continue
                extracted = self.extract_pending_interaction(
                    parsed,
                    fallback_interaction_id=fallback_interaction_id,
                )
                if extracted is not None:
                    return extracted
            return None

        try:
            parsed = adapter.parse_runtime_stream(
                stdout_raw=(raw_stdout or "").encode("utf-8", errors="replace"),
                stderr_raw=(raw_stderr or "").encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
            messages = parsed.get("assistant_messages") if isinstance(parsed, dict) else None
            if isinstance(messages, list):
                for item in reversed(messages):
                    if not isinstance(item, dict):
                        continue
                    text_obj = item.get("text")
                    if not isinstance(text_obj, str) or not text_obj.strip():
                        continue
                    extracted = _extract_from_text(text_obj)
                    if extracted is not None:
                        return extracted
        except Exception as exc:
            # Third-party parser boundary: fall back to raw stream scanning path.
            logger.warning(
                "interactive lifecycle stream extraction parse failed",
                extra={
                    "component": "orchestration.run_interaction_lifecycle_service",
                    "action": "extract_pending_interaction_from_stream.parse_runtime_stream",
                    "error_type": type(exc).__name__,
                    "fallback": "scan_raw_stdout_stderr",
                },
                exc_info=True,
            )

        stream_text = "\n".join(part for part in [raw_stdout or "", raw_stderr or ""] if isinstance(part, str))
        if not stream_text.strip():
            return None
        extracted = _extract_from_text(stream_text)
        if extracted is not None:
            return extracted
        return None

    def strip_done_marker_for_output_validation(
        self,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        if not isinstance(payload, dict):
            return {}, False
        marker_value = payload.get("__SKILL_DONE__")
        if "__SKILL_DONE__" not in payload:
            return dict(payload), False
        sanitized = dict(payload)
        sanitized.pop("__SKILL_DONE__", None)
        return sanitized, marker_value is True

    async def persist_waiting_interaction(
        self,
        *,
        run_id: str,
        run_dir: Path,
        request_id: str,
        attempt_number: int,
        profile: EngineInteractiveProfile,
        interactive_auto_reply: bool,
        pending_interaction: dict[str, Any],
        run_store_backend: Any,
        append_internal_schema_warning: Callable[..., None],
        append_orchestrator_event: Callable[..., None],
    ) -> str | None:
        pending_interaction.setdefault("source_attempt", attempt_number)
        try:
            validate_pending_interaction(pending_interaction)
        except ProtocolSchemaViolation as exc:
            append_internal_schema_warning(
                run_dir=run_dir,
                attempt_number=attempt_number,
                schema_path="pending_interaction",
                detail=str(exc),
            )
            pending_interaction = {
                "interaction_id": int(pending_interaction.get("interaction_id", attempt_number)),
                "source_attempt": attempt_number,
                "kind": "open_text",
                "prompt": (
                    self.normalize_interaction_prompt(pending_interaction.get("prompt"))
                    if isinstance(pending_interaction.get("prompt"), str)
                    else ""
                )
                or (
                    self.normalize_interaction_prompt(pending_interaction.get("ui_hints", {}).get("hint"))
                    if isinstance(pending_interaction.get("ui_hints"), dict)
                    and isinstance(pending_interaction.get("ui_hints", {}).get("hint"), str)
                    else ""
                )
                or DEFAULT_INTERACTION_PROMPT,
                "options": [],
                "ui_hints": {},
                "default_decision_policy": "engine_judgement",
                "required_fields": [],
            }
        await maybe_await(run_store_backend.set_pending_interaction(request_id, pending_interaction))
        await maybe_await(run_store_backend.set_interactive_profile(request_id, profile.model_dump(mode="json")))
        await maybe_await(run_store_backend.append_interaction_history(
            request_id=request_id,
            interaction_id=int(pending_interaction["interaction_id"]),
            event_type="ask_user",
            payload=pending_interaction,
            source_attempt=attempt_number,
        ))
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="interaction",
            type_name=OrchestratorEventType.INTERACTION_USER_INPUT_REQUIRED.value,
            data={
                "interaction_id": int(pending_interaction["interaction_id"]),
                "kind": str(pending_interaction.get("kind", "open_text")),
            },
        )
        _ = run_id
        _ = interactive_auto_reply
        handle = await maybe_await(run_store_backend.get_engine_session_handle(request_id))
        if not isinstance(handle, dict) or not isinstance(handle.get("handle_value"), str) or not str(handle.get("handle_value")).strip():
            return InteractiveErrorCode.SESSION_RESUME_FAILED.value
        await self.write_interaction_mirror_files(
            run_dir=run_dir,
            request_id=request_id,
            pending_interaction=pending_interaction,
            run_store_backend=run_store_backend,
        )
        await run_projection_service.write_non_terminal_projection(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            status=RunStatus.WAITING_USER,
            current_attempt=attempt_number,
            pending_owner=PendingOwner.WAITING_USER,
            pending_interaction=pending_interaction,
            source_attempt=attempt_number,
            effective_session_timeout_sec=profile.session_timeout_sec,
            run_store_backend=run_store_backend,
        )
        return None

    async def write_interaction_mirror_files(
        self,
        *,
        run_dir: Path,
        request_id: str,
        pending_interaction: dict[str, Any],
        run_store_backend: Any,
    ) -> None:
        _ = run_dir
        _ = request_id
        _ = pending_interaction
        _ = run_store_backend

    async def auto_decide_after_timeout(
        self,
        *,
        request_id: str,
        run_id: str,
        delay_sec: int,
        run_store_backend: Any,
        workspace_backend: Any,
        update_status: Callable[..., None],
        run_job_callback: Callable[..., Awaitable[None]],
        append_internal_schema_warning: Callable[..., None],
        resolve_attempt_number: Callable[..., Awaitable[int]],
    ) -> None:
        await asyncio.sleep(max(0, int(delay_sec)))
        request_record = await maybe_await(run_store_backend.get_request(request_id))
        if not request_record or request_record.get("run_id") != run_id:
            return
        run_dir = workspace_backend.get_run_dir(run_id)
        if run_dir is None:
            return
        status_file = run_dir / ".state" / "state.json"
        if not status_file.exists():
            return
        payload = json.loads(status_file.read_text(encoding="utf-8"))
        current_status = RunStatus(payload.get("status", RunStatus.QUEUED.value))
        if current_status != RunStatus.WAITING_USER:
            return
        pending_interaction = await maybe_await(run_store_backend.get_pending_interaction(request_id))
        if pending_interaction is None:
            return
        runtime_options = request_record.get(
            "effective_runtime_options",
            request_record.get("runtime_options", {}),
        )
        interactive_auto_reply = bool(
            runtime_options.get("interactive_auto_reply", False)
        )
        if not timeout_requires_auto_decision(interactive_auto_reply):
            return
        await self.resume_with_auto_decision(
            request_record=request_record,
            run_id=run_id,
            request_id=request_id,
            pending_interaction=pending_interaction,
            run_store_backend=run_store_backend,
            workspace_backend=workspace_backend,
            update_status=update_status,
            run_job_callback=run_job_callback,
            append_internal_schema_warning=append_internal_schema_warning,
            resolve_attempt_number=resolve_attempt_number,
        )

    async def resume_with_auto_decision(
        self,
        *,
        request_record: dict[str, Any],
        run_id: str,
        request_id: str,
        pending_interaction: dict[str, Any],
        run_store_backend: Any,
        workspace_backend: Any,
        update_status: Callable[..., None],
        run_job_callback: Callable[..., Awaitable[None]],
        append_internal_schema_warning: Callable[..., None],
        resolve_attempt_number: Callable[..., Awaitable[int]],
    ) -> None:
        interaction_id_obj = pending_interaction.get("interaction_id")
        if isinstance(interaction_id_obj, int):
            interaction_id = interaction_id_obj
        elif isinstance(interaction_id_obj, str):
            try:
                interaction_id = int(interaction_id_obj)
            except (TypeError, ValueError):
                return
        else:
            return
        if interaction_id <= 0:
            return

        default_policy_obj = pending_interaction.get("default_decision_policy")
        default_policy = (
            default_policy_obj.strip()
            if isinstance(default_policy_obj, str) and default_policy_obj.strip()
            else "engine_judgement"
        )
        source_attempt_obj = pending_interaction.get("source_attempt")
        source_attempt = source_attempt_obj if isinstance(source_attempt_obj, int) else 1
        auto_reply_payload = {
            "source": "auto_decide_timeout",
            "interaction_id": interaction_id,
            "reason": "user_no_reply",
            "policy": default_policy,
            "instruction": (
                "User did not respond in time. Continue with your best judgement "
                "based on the current context."
            ),
        }
        resume_command = make_resume_command(
            interaction_id=interaction_id,
            response=auto_reply_payload,
            resolution_mode=InteractiveResolutionMode.AUTO_DECIDE_TIMEOUT.value,
            auto_decide_reason="user_no_reply",
            auto_decide_policy=default_policy,
        )
        try:
            validate_resume_command(resume_command)
        except ProtocolSchemaViolation as exc:
            append_internal_schema_warning(
                run_dir=workspace_backend.get_run_dir(run_id) or Path(config.SYSTEM.RUNS_DIR) / run_id,
                attempt_number=await resolve_attempt_number(request_id=request_id, is_interactive=True),
                schema_path="interactive_resume_command",
                detail=str(exc),
            )
            resume_command = make_resume_command(
                interaction_id=interaction_id,
                response=auto_reply_payload,
                resolution_mode=InteractiveResolutionMode.USER_REPLY.value,
            )
        reply_state = await maybe_await(run_store_backend.submit_interaction_reply(
            request_id=request_id,
            interaction_id=interaction_id,
            response=resume_command["response"],
            idempotency_key=f"auto-timeout:{interaction_id}",
        ))
        if reply_state not in {"accepted", "idempotent"}:
            return

        next_status = waiting_reply_target_status()
        run_dir = workspace_backend.get_run_dir(run_id)
        if run_dir is None:
            return
        await maybe_await(run_store_backend.update_run_status(run_id, next_status))

        options = {
            **request_record.get("engine_options", {}),
            **request_record.get(
                "effective_runtime_options",
                request_record.get("runtime_options", {}),
            ),
            "__interactive_reply_payload": resume_command["response"],
            "__interactive_reply_interaction_id": resume_command["interaction_id"],
            "__interactive_resolution_mode": resume_command["resolution_mode"],
            "__interactive_auto_reason": resume_command.get("auto_decide_reason"),
            "__interactive_auto_policy": resume_command.get("auto_decide_policy"),
            "__interactive_source_attempt": source_attempt,
            "__attempt_number_override": source_attempt + 1,
        }
        resume_ticket = await maybe_await(
            run_store_backend.issue_resume_ticket(
                request_id,
                cause=ResumeCause.INTERACTION_AUTO_DECIDE_TIMEOUT.value,
                source_attempt=source_attempt,
                target_attempt=source_attempt + 1,
                payload={
                    "interaction_id": interaction_id,
                    "resolution_mode": resume_command["resolution_mode"],
                    "response": resume_command["response"],
                },
            )
        )
        await run_projection_service.write_non_terminal_projection(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            status=next_status,
            current_attempt=source_attempt,
            pending_owner=None,
            resume_ticket_id=str(resume_ticket["ticket_id"]),
            resume_cause=ResumeCause.INTERACTION_AUTO_DECIDE_TIMEOUT,
            source_attempt=source_attempt,
            target_attempt=source_attempt + 1,
            effective_session_timeout_sec=await maybe_await(
                run_store_backend.get_effective_session_timeout(request_id)
            ),
            run_store_backend=run_store_backend,
        )
        options["__resume_ticket_id"] = str(resume_ticket["ticket_id"])
        options["__resume_cause"] = ResumeCause.INTERACTION_AUTO_DECIDE_TIMEOUT.value
        ticket_dispatched = await maybe_await(
            run_store_backend.mark_resume_ticket_dispatched(
                request_id,
                str(resume_ticket["ticket_id"]),
            )
        )
        if ticket_dispatched:
            await run_job_callback(
                run_id=run_id,
                skill_id=str(request_record["skill_id"]),
                engine_name=str(request_record["engine"]),
                options=options,
                cache_key=None,
            )
