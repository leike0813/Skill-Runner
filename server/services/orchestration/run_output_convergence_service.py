from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from server.models import ExecutionMode, OrchestratorEventType, SkillManifest
from server.runtime.adapter.common.structured_output_pipeline import structured_output_pipeline
from server.runtime.protocol.final_promotion_coordinator import resolve_message_id
from server.runtime.auth_detection.types import AuthDetectionResult
from server.services.orchestration.run_output_schema_service import run_output_schema_service
from server.services.orchestration.run_result_file_fallback import resolve_result_file_fallback
from server.services.platform.async_compat import maybe_await


MAX_REPAIR_ROUNDS = 3
WARNING_OUTPUT_SCHEMA_REPAIR_CONVERGED = "OUTPUT_SCHEMA_REPAIR_CONVERGED"
WARNING_OUTPUT_SCHEMA_REPAIR_EXHAUSTED = "OUTPUT_SCHEMA_REPAIR_EXHAUSTED"
WARNING_OUTPUT_SCHEMA_REPAIR_SKIPPED_NO_SESSION_HANDLE = "OUTPUT_SCHEMA_REPAIR_SKIPPED_NO_SESSION_HANDLE"


@dataclass(frozen=True)
class OutputRepairRoundRecord:
    attempt_number: int
    internal_round_index: int
    repair_stage: str
    candidate_source: str
    executor: str
    validation_errors: list[str]
    repair_prompt_or_summary: str
    converged: bool
    legacy_fallback_target: str | None
    raw_candidate_present: bool
    deterministic_repair_applied: bool
    deterministic_repair_succeeded: bool
    schema_valid: bool
    branch_resolved: str | None
    target_contract_mode: str
    repair_level: str
    resume_handle_reused: bool
    outcome: str


@dataclass
class OutputConvergenceResult:
    output_data: dict[str, Any] = field(default_factory=dict)
    has_structured_output: bool = False
    structured_output_source: str | None = None
    done_signal_found: bool = False
    schema_output_errors: list[str] = field(default_factory=list)
    repair_level: str = "none"
    validation_warnings: list[str] = field(default_factory=list)
    pending_interaction_candidate: dict[str, Any] | None = None
    convergence_state: str = "not_needed"
    legacy_fallback_target: str | None = None
    process_exit_code: int | None = None
    process_failure_reason: str | None = None
    auth_detection_result: AuthDetectionResult | None = None
    branch_resolved: str | None = None
    turn_payload_for_completion: dict[str, Any] = field(default_factory=dict)
    runtime_parse_result: dict[str, Any] | None = None
    engine_result: Any | None = None


@dataclass(frozen=True)
class _CandidateResolution:
    payload: dict[str, Any] | None
    source: str
    repair_level: str
    raw_candidate_present: bool
    deterministic_repair_applied: bool
    deterministic_repair_succeeded: bool
    raw_candidate_preview: str
    message_id: str | None
    message_family_id: str | None


class RunOutputConvergenceService:
    async def converge(
        self,
        *,
        adapter: Any,
        skill: SkillManifest,
        input_data: dict[str, Any],
        run_dir: Path,
        request_id: str | None,
        run_store_backend: Any,
        run_id: str,
        engine_name: str,
        execution_mode: str,
        attempt_number: int,
        options: dict[str, Any],
        initial_result: Any,
        initial_runtime_parse_result: dict[str, Any] | None,
        auth_detection_result: AuthDetectionResult,
        auth_detection_high: bool,
        resolve_structured_output_candidate: Callable[..., dict[str, Any] | None],
        strip_done_marker_for_output_validation: Callable[[dict[str, Any]], tuple[dict[str, Any], bool]],
        extract_pending_interaction: Callable[..., dict[str, Any] | None],
        append_orchestrator_event: Callable[..., None],
        append_output_repair_record: Callable[..., None],
        live_runtime_emitter_factory: Callable[[], Any],
    ) -> OutputConvergenceResult:
        result = initial_result
        runtime_parse_result = initial_runtime_parse_result
        validation_warnings: list[str] = []
        target_schema = run_output_schema_service.resolve_target_schema(
            skill=skill,
            execution_mode=execution_mode,
            run_dir=run_dir,
        )
        target_contract_mode = (
            "interactive_union"
            if (execution_mode or "").strip().lower() == ExecutionMode.INTERACTIVE.value
            else "auto_final"
        )
        prompt_contract_markdown = structured_output_pipeline.resolve_prompt_contract_markdown(
            engine_name=engine_name,
            run_dir=run_dir,
            options=options,
        )
        legacy_fallback_target = "legacy_lifecycle_fallback"
        handle = await self._resolve_session_handle(
            request_id=request_id,
            run_store_backend=run_store_backend,
            options=options,
        )

        candidate = self._resolve_candidate(
            adapter=adapter,
            result=result,
            runtime_parse_result=runtime_parse_result,
            execution_mode=execution_mode,
            engine_name=engine_name,
            run_dir=run_dir,
            options=options,
            resolve_structured_output_candidate=resolve_structured_output_candidate,
            message_family_id=None,
            attempt_number=attempt_number,
        )
        resolved = self._resolve_branch(
            execution_mode=execution_mode,
            attempt_number=attempt_number,
            candidate_payload=candidate.payload,
            target_schema=target_schema,
            strip_done_marker_for_output_validation=strip_done_marker_for_output_validation,
            extract_pending_interaction=extract_pending_interaction,
        )
        if resolved is not None and not resolved.schema_errors:
            return self._build_result(
                engine_result=result,
                runtime_parse_result=runtime_parse_result,
                auth_detection_result=auth_detection_result,
                output_data=resolved.output_data,
                has_structured_output=True,
                structured_output_source=candidate.source,
                done_signal_found=resolved.done_signal_found,
                schema_output_errors=[],
                repair_level=candidate.repair_level,
                validation_warnings=validation_warnings,
                pending_interaction_candidate=resolved.pending_interaction_candidate,
                convergence_state="not_needed",
                legacy_fallback_target=None,
                process_exit_code=getattr(result, "exit_code", None),
                process_failure_reason=self._sanitized_failure_reason(
                    result=result,
                    auth_detection_high=auth_detection_high,
                ),
                branch_resolved=resolved.branch_resolved,
            )

        legacy_output_data, legacy_done_signal_found, legacy_has_structured_output = (
            self._build_legacy_candidate_projection(
                candidate_payload=candidate.payload,
                strip_done_marker_for_output_validation=strip_done_marker_for_output_validation,
            )
        )
        skip_reason = self._resolve_skip_reason(
            result=result,
            auth_detection_high=auth_detection_high,
            handle=handle,
            target_schema=target_schema,
        )
        if skip_reason is not None:
            append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="diagnostic",
                type_name=OrchestratorEventType.OUTPUT_REPAIR_SKIPPED.value,
                data={
                    "internal_round_index": 0,
                    "repair_stage": "schema_repair_rounds",
                    "candidate_source": candidate.source,
                    "skip_reason": skip_reason,
                    "legacy_fallback_target": legacy_fallback_target,
                },
                engine_name=engine_name,
            )
            append_output_repair_record(
                run_dir=run_dir,
                attempt_number=attempt_number,
                record=self._round_record(
                    attempt_number=attempt_number,
                    internal_round_index=0,
                    candidate_source=candidate.source,
                    validation_errors=resolved.schema_errors if resolved is not None else [],
                    prompt_summary=prompt_contract_markdown,
                    converged=False,
                    legacy_fallback_target=legacy_fallback_target,
                    raw_candidate_present=candidate.raw_candidate_present,
                    deterministic_repair_applied=candidate.deterministic_repair_applied,
                    deterministic_repair_succeeded=candidate.deterministic_repair_succeeded,
                    schema_valid=False,
                    branch_resolved=None,
                    target_contract_mode=target_contract_mode,
                    repair_level=candidate.repair_level,
                    resume_handle_reused=False,
                    outcome="skipped",
                ),
            )
            if skip_reason == "missing_session_handle":
                validation_warnings.append(WARNING_OUTPUT_SCHEMA_REPAIR_SKIPPED_NO_SESSION_HANDLE)
            if skip_reason in {"auth_required", "process_exit_nonzero"}:
                return self._build_result(
                    engine_result=result,
                    runtime_parse_result=runtime_parse_result,
                    auth_detection_result=auth_detection_result,
                    output_data=legacy_output_data,
                    has_structured_output=legacy_has_structured_output,
                    structured_output_source=candidate.source,
                    done_signal_found=legacy_done_signal_found,
                    schema_output_errors=(
                        resolved.schema_errors
                        if resolved is not None
                        else self._default_errors_for_candidate(candidate)
                    ),
                    repair_level=candidate.repair_level,
                    validation_warnings=validation_warnings,
                    pending_interaction_candidate=None,
                    convergence_state="skipped",
                    legacy_fallback_target=legacy_fallback_target,
                    process_exit_code=getattr(result, "exit_code", None),
                    process_failure_reason=self._sanitized_failure_reason(
                        result=result,
                        auth_detection_high=auth_detection_high,
                    ),
                    branch_resolved=None,
                )
            fallback = self._apply_result_file_fallback(
                skill=skill,
                run_dir=run_dir,
                execution_mode=execution_mode,
                attempt_number=attempt_number,
                current_errors=(
                    resolved.schema_errors
                    if resolved is not None
                    else self._default_errors_for_candidate(candidate)
                ),
                validation_warnings=validation_warnings,
                extract_pending_interaction=extract_pending_interaction,
            )
            return self._build_result(
                engine_result=result,
                runtime_parse_result=runtime_parse_result,
                auth_detection_result=auth_detection_result,
                output_data=fallback.output_data or legacy_output_data,
                has_structured_output=(
                    fallback.has_structured_output or legacy_has_structured_output
                ),
                structured_output_source=fallback.structured_output_source or candidate.source,
                done_signal_found=(
                    fallback.done_signal_found or legacy_done_signal_found
                ),
                schema_output_errors=fallback.schema_output_errors,
                repair_level=candidate.repair_level,
                validation_warnings=validation_warnings,
                pending_interaction_candidate=fallback.pending_interaction_candidate,
                convergence_state="skipped",
                legacy_fallback_target=legacy_fallback_target,
                process_exit_code=getattr(result, "exit_code", None),
                process_failure_reason=self._sanitized_failure_reason(
                    result=result,
                    auth_detection_high=auth_detection_high,
                ),
                branch_resolved=fallback.branch_resolved,
            )

        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="diagnostic",
            type_name=OrchestratorEventType.OUTPUT_REPAIR_STARTED.value,
            data={
                "internal_round_index": 0,
                "repair_stage": "schema_repair_rounds",
                "candidate_source": candidate.source,
                "reason": "target output did not satisfy the attempt contract",
            },
            engine_name=engine_name,
        )
        self._append_supersede_event(
            append_orchestrator_event=append_orchestrator_event,
            run_dir=run_dir,
            attempt_number=attempt_number,
            engine_name=engine_name,
            candidate=candidate,
            repair_round_index=1,
        )

        last_errors = (
            resolved.schema_errors if resolved is not None else self._default_errors_for_candidate(candidate)
        )
        last_candidate = candidate
        last_result = result
        last_runtime_parse_result = runtime_parse_result
        repair_message_family_id = candidate.message_family_id or candidate.message_id
        for round_index in range(1, MAX_REPAIR_ROUNDS + 1):
            repair_prompt = self._build_repair_prompt(
                execution_mode=execution_mode,
                candidate=last_candidate,
                schema_errors=last_errors,
                prompt_summary=prompt_contract_markdown,
            )
            append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="diagnostic",
                type_name=OrchestratorEventType.OUTPUT_REPAIR_ROUND_STARTED.value,
                data={
                    "internal_round_index": round_index,
                    "repair_stage": "schema_repair_rounds",
                    "candidate_source": last_candidate.source,
                    "reason": "retrying with a strict schema repair prompt",
                },
                engine_name=engine_name,
            )
            rerun_options = dict(options)
            rerun_options["__repair_round_index"] = round_index
            rerun_options["__prompt_override"] = repair_prompt
            rerun_options["__resume_session_handle"] = handle
            emitter = self._build_live_runtime_emitter(
                live_runtime_emitter_factory=live_runtime_emitter_factory,
                message_family_id=repair_message_family_id,
            )
            rerun_result = await self._run_adapter(
                adapter=adapter,
                skill=skill,
                input_data=input_data,
                run_dir=run_dir,
                options=rerun_options,
                live_runtime_emitter=emitter,
            )
            rerun_parse_result = self._parse_runtime_stream(
                adapter=adapter,
                raw_stdout=getattr(rerun_result, "raw_stdout", "") or "",
                raw_stderr=getattr(rerun_result, "raw_stderr", "") or "",
            )
            handle = await self._resolve_session_handle(
                request_id=request_id,
                run_store_backend=run_store_backend,
                options=rerun_options,
            )
            round_candidate = self._resolve_candidate(
                adapter=adapter,
                result=rerun_result,
                runtime_parse_result=rerun_parse_result,
                execution_mode=execution_mode,
                engine_name=engine_name,
                run_dir=run_dir,
                options=rerun_options,
                resolve_structured_output_candidate=resolve_structured_output_candidate,
                message_family_id=repair_message_family_id,
                attempt_number=attempt_number,
            )
            round_resolved = self._resolve_branch(
                execution_mode=execution_mode,
                attempt_number=attempt_number,
                candidate_payload=round_candidate.payload,
                target_schema=target_schema,
                strip_done_marker_for_output_validation=strip_done_marker_for_output_validation,
                extract_pending_interaction=extract_pending_interaction,
            )
            round_errors = round_resolved.schema_errors if round_resolved is not None else ["Target output validation failed"]
            schema_valid = round_resolved is not None and not round_errors
            append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="diagnostic",
                type_name=OrchestratorEventType.OUTPUT_REPAIR_ROUND_COMPLETED.value,
                data={
                    "internal_round_index": round_index,
                    "repair_stage": "schema_repair_rounds",
                    "candidate_source": round_candidate.source,
                    "reason": "schema validated" if schema_valid else "schema still invalid",
                },
                engine_name=engine_name,
            )
            append_output_repair_record(
                run_dir=run_dir,
                attempt_number=attempt_number,
                record=self._round_record(
                    attempt_number=attempt_number,
                    internal_round_index=round_index,
                    candidate_source=round_candidate.source,
                    validation_errors=round_errors,
                    prompt_summary=repair_prompt,
                    converged=schema_valid,
                    legacy_fallback_target=None,
                    raw_candidate_present=round_candidate.raw_candidate_present,
                    deterministic_repair_applied=round_candidate.deterministic_repair_applied,
                    deterministic_repair_succeeded=round_candidate.deterministic_repair_succeeded,
                    schema_valid=schema_valid,
                    branch_resolved=round_resolved.branch_resolved if round_resolved is not None else None,
                    target_contract_mode=target_contract_mode,
                    repair_level=round_candidate.repair_level,
                    resume_handle_reused=True,
                    outcome="converged" if schema_valid else "retry",
                ),
            )
            if schema_valid and round_resolved is not None:
                validation_warnings.append(WARNING_OUTPUT_SCHEMA_REPAIR_CONVERGED)
                append_orchestrator_event(
                    run_dir=run_dir,
                    attempt_number=attempt_number,
                    category="diagnostic",
                    type_name=OrchestratorEventType.OUTPUT_REPAIR_CONVERGED.value,
                    data={
                        "internal_round_index": round_index,
                        "repair_stage": "schema_repair_rounds",
                        "candidate_source": round_candidate.source,
                        "reason": "repair produced a valid payload",
                    },
                    engine_name=engine_name,
                )
                return self._build_result(
                    engine_result=rerun_result,
                    runtime_parse_result=rerun_parse_result,
                    auth_detection_result=auth_detection_result,
                    output_data=round_resolved.output_data,
                    has_structured_output=True,
                    structured_output_source=round_candidate.source,
                    done_signal_found=round_resolved.done_signal_found,
                    schema_output_errors=[],
                    repair_level=round_candidate.repair_level,
                    validation_warnings=validation_warnings,
                    pending_interaction_candidate=round_resolved.pending_interaction_candidate,
                    convergence_state="converged",
                    legacy_fallback_target=None,
                    process_exit_code=getattr(rerun_result, "exit_code", None),
                    process_failure_reason=self._sanitized_failure_reason(
                        result=rerun_result,
                        auth_detection_high=auth_detection_high,
                    ),
                    branch_resolved=round_resolved.branch_resolved,
                )
            if round_index < MAX_REPAIR_ROUNDS:
                self._append_supersede_event(
                    append_orchestrator_event=append_orchestrator_event,
                    run_dir=run_dir,
                    attempt_number=attempt_number,
                    engine_name=engine_name,
                    candidate=round_candidate,
                    repair_round_index=round_index + 1,
                )
            last_candidate = round_candidate
            last_errors = round_errors
            last_result = rerun_result
            last_runtime_parse_result = rerun_parse_result

        validation_warnings.append(WARNING_OUTPUT_SCHEMA_REPAIR_EXHAUSTED)
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="diagnostic",
            type_name=OrchestratorEventType.OUTPUT_REPAIR_EXHAUSTED.value,
            data={
                "internal_round_index": MAX_REPAIR_ROUNDS,
                "repair_stage": "schema_repair_rounds",
                "candidate_source": last_candidate.source,
                "reason": "bounded schema repair rounds were exhausted",
                "legacy_fallback_target": legacy_fallback_target,
            },
            engine_name=engine_name,
        )
        append_output_repair_record(
            run_dir=run_dir,
            attempt_number=attempt_number,
            record=self._round_record(
                attempt_number=attempt_number,
                internal_round_index=MAX_REPAIR_ROUNDS,
                candidate_source=last_candidate.source,
                validation_errors=last_errors,
                prompt_summary=prompt_contract_markdown,
                converged=False,
                legacy_fallback_target=legacy_fallback_target,
                raw_candidate_present=last_candidate.raw_candidate_present,
                deterministic_repair_applied=last_candidate.deterministic_repair_applied,
                deterministic_repair_succeeded=last_candidate.deterministic_repair_succeeded,
                schema_valid=False,
                branch_resolved=None,
                target_contract_mode=target_contract_mode,
                repair_level=last_candidate.repair_level,
                resume_handle_reused=True,
                outcome="exhausted",
            ),
        )
        self._append_supersede_event(
            append_orchestrator_event=append_orchestrator_event,
            run_dir=run_dir,
            attempt_number=attempt_number,
            engine_name=engine_name,
            candidate=last_candidate,
            repair_round_index=MAX_REPAIR_ROUNDS + 1,
        )
        fallback = self._apply_result_file_fallback(
            skill=skill,
            run_dir=run_dir,
            execution_mode=execution_mode,
            attempt_number=attempt_number,
            current_errors=last_errors,
            validation_warnings=validation_warnings,
            extract_pending_interaction=extract_pending_interaction,
        )
        exhausted_output_data, exhausted_done_signal_found, exhausted_has_structured_output = (
            self._build_legacy_candidate_projection(
                candidate_payload=last_candidate.payload,
                strip_done_marker_for_output_validation=strip_done_marker_for_output_validation,
            )
        )
        return self._build_result(
            engine_result=last_result,
            runtime_parse_result=last_runtime_parse_result,
            auth_detection_result=auth_detection_result,
            output_data=fallback.output_data or exhausted_output_data,
            has_structured_output=(
                fallback.has_structured_output or exhausted_has_structured_output
            ),
            structured_output_source=fallback.structured_output_source or last_candidate.source,
            done_signal_found=(
                fallback.done_signal_found or exhausted_done_signal_found
            ),
            schema_output_errors=fallback.schema_output_errors,
            repair_level=last_candidate.repair_level,
            validation_warnings=validation_warnings,
            pending_interaction_candidate=fallback.pending_interaction_candidate,
            convergence_state="exhausted",
            legacy_fallback_target=legacy_fallback_target,
            process_exit_code=getattr(last_result, "exit_code", None),
            process_failure_reason=self._sanitized_failure_reason(
                result=last_result,
                auth_detection_high=auth_detection_high,
            ),
            branch_resolved=fallback.branch_resolved,
        )

    def _resolve_candidate(
        self,
        *,
        adapter: Any,
        result: Any,
        runtime_parse_result: dict[str, Any] | None,
        execution_mode: str,
        engine_name: str,
        run_dir: Path,
        options: dict[str, Any],
        resolve_structured_output_candidate: Callable[..., dict[str, Any] | None],
        message_family_id: str | None,
        attempt_number: int,
    ) -> _CandidateResolution:
        candidate_message_id, resolved_family_id = self._resolve_candidate_identity(
            runtime_parse_result=runtime_parse_result,
            raw_stdout=getattr(result, "raw_stdout", "") or "",
            fallback_family_id=message_family_id,
            attempt_number=attempt_number,
        )
        candidate_text = self._extract_candidate_text(
            runtime_parse_result=runtime_parse_result,
            raw_stdout=getattr(result, "raw_stdout", "") or "",
        )
        if candidate_text:
            parsed, repair_level = self._parse_json_with_deterministic_repair(adapter, candidate_text)
            if isinstance(parsed, dict):
                payload = self._canonicalize_candidate_payload(
                    engine_name=engine_name,
                    run_dir=run_dir,
                    options=options,
                    payload=parsed,
                )
                return _CandidateResolution(
                    payload=payload,
                    source="deterministic_parse",
                    repair_level=repair_level or "none",
                    raw_candidate_present=True,
                    deterministic_repair_applied=True,
                    deterministic_repair_succeeded=True,
                    raw_candidate_preview=candidate_text[:500],
                    message_id=candidate_message_id,
                    message_family_id=resolved_family_id,
                )
        structured_candidate = resolve_structured_output_candidate(
            result=result,
            runtime_parse_result=runtime_parse_result,
            execution_mode=execution_mode,
        )
        if isinstance(structured_candidate, dict):
            payload_obj = structured_candidate.get("payload")
            source_obj = structured_candidate.get("source")
            source: str = source_obj if isinstance(source_obj, str) else "structured_candidate"
            if isinstance(payload_obj, dict):
                repair_level = getattr(result, "repair_level", "none") or "none"
                canonical_payload = self._canonicalize_candidate_payload(
                    engine_name=engine_name,
                    run_dir=run_dir,
                    options=options,
                    payload=payload_obj,
                )
                return _CandidateResolution(
                    payload=canonical_payload,
                    source=source,
                    repair_level=repair_level,
                    raw_candidate_present=True,
                    deterministic_repair_applied=repair_level != "none",
                    deterministic_repair_succeeded=repair_level != "none",
                    raw_candidate_preview=self._candidate_preview_from_payload(payload_obj),
                    message_id=candidate_message_id,
                    message_family_id=resolved_family_id,
                )
        if candidate_text:
            return _CandidateResolution(
                payload=None,
                source="deterministic_parse",
                repair_level="none",
                raw_candidate_present=True,
                deterministic_repair_applied=True,
                deterministic_repair_succeeded=False,
                raw_candidate_preview=candidate_text[:500],
                message_id=candidate_message_id,
                message_family_id=resolved_family_id,
            )
        return _CandidateResolution(
            payload=None,
            source="no_structured_candidate",
            repair_level="none",
            raw_candidate_present=False,
            deterministic_repair_applied=False,
            deterministic_repair_succeeded=False,
            raw_candidate_preview="",
            message_id=candidate_message_id,
            message_family_id=resolved_family_id,
        )

    def _canonicalize_candidate_payload(
        self,
        *,
        engine_name: str,
        run_dir: Path,
        options: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        canonical = structured_output_pipeline.canonicalize_payload(
            engine_name=engine_name,
            run_dir=run_dir,
            options=options,
            payload=payload,
        )
        return dict(canonical)

    def _resolve_candidate_identity(
        self,
        *,
        runtime_parse_result: dict[str, Any] | None,
        raw_stdout: str,
        fallback_family_id: str | None,
        attempt_number: int,
    ) -> tuple[str | None, str | None]:
        assistant_messages = (
            runtime_parse_result.get("assistant_messages")
            if isinstance(runtime_parse_result, dict)
            else None
        )
        if not isinstance(assistant_messages, list):
            return None, fallback_family_id
        for item in reversed(assistant_messages):
            if not isinstance(item, dict):
                continue
            text_obj = item.get("text")
            text = text_obj if isinstance(text_obj, str) and text_obj.strip() else raw_stdout
            if not isinstance(text, str) or not text.strip():
                continue
            raw_ref_obj = item.get("raw_ref")
            raw_ref = raw_ref_obj if isinstance(raw_ref_obj, dict) else None
            message_id = resolve_message_id(
                message_id=item.get("message_id") if isinstance(item.get("message_id"), str) else None,
                text=text,
                attempt_number=attempt_number,
                raw_ref=raw_ref,
            )
            message_family_id = (
                fallback_family_id
                or (item.get("message_family_id") if isinstance(item.get("message_family_id"), str) else None)
                or message_id
            )
            return message_id, message_family_id
        return None, fallback_family_id

    def _append_supersede_event(
        self,
        *,
        append_orchestrator_event: Callable[..., None],
        run_dir: Path,
        attempt_number: int,
        engine_name: str,
        candidate: _CandidateResolution,
        repair_round_index: int,
    ) -> None:
        if not isinstance(candidate.message_id, str) or not candidate.message_id.strip():
            return
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="diagnostic",
            type_name=OrchestratorEventType.ASSISTANT_MESSAGE_SUPERSEDED.value,
            data={
                "message_id": candidate.message_id,
                "message_family_id": candidate.message_family_id or candidate.message_id,
                "reason": "output_repair_started",
                "repair_round_index": repair_round_index,
                "replacement_expected": True,
            },
            engine_name=engine_name,
        )

    def _build_live_runtime_emitter(
        self,
        *,
        live_runtime_emitter_factory: Callable[..., Any],
        message_family_id: str | None,
    ) -> Any:
        if not isinstance(message_family_id, str) or not message_family_id.strip():
            return live_runtime_emitter_factory()
        try:
            return live_runtime_emitter_factory(message_family_id=message_family_id)
        except TypeError:
            return live_runtime_emitter_factory()

    async def _resolve_session_handle(
        self,
        *,
        request_id: str | None,
        run_store_backend: Any,
        options: dict[str, Any],
    ) -> dict[str, Any] | None:
        handle = options.get("__resume_session_handle")
        if isinstance(handle, dict):
            return handle
        if not isinstance(request_id, str) or not request_id.strip():
            return None
        loaded = await maybe_await(run_store_backend.get_engine_session_handle(request_id))
        return loaded if isinstance(loaded, dict) else None

    def _resolve_skip_reason(
        self,
        *,
        result: Any,
        auth_detection_high: bool,
        handle: dict[str, Any] | None,
        target_schema: dict[str, Any] | None,
    ) -> str | None:
        exit_code = getattr(result, "exit_code", None)
        if exit_code is not None and int(exit_code) != 0:
            return "process_exit_nonzero"
        if auth_detection_high:
            return "auth_required"
        if not isinstance(target_schema, dict):
            return "missing_target_schema"
        if handle is None:
            return "missing_session_handle"
        return None

    def _resolve_branch(
        self,
        *,
        execution_mode: str,
        attempt_number: int,
        candidate_payload: dict[str, Any] | None,
        target_schema: dict[str, Any] | None,
        strip_done_marker_for_output_validation: Callable[[dict[str, Any]], tuple[dict[str, Any], bool]],
        extract_pending_interaction: Callable[..., dict[str, Any] | None],
    ) -> _ResolvedBranch | None:
        if not isinstance(candidate_payload, dict):
            return None
        schema_errors = run_output_schema_service.validate_target_output(
            schema=target_schema,
            payload=candidate_payload,
        )
        if schema_errors:
            return _ResolvedBranch(
                output_data={},
                pending_interaction_candidate=None,
                done_signal_found=False,
                schema_errors=schema_errors,
                branch_resolved=None,
            )
        if (execution_mode or "").strip().lower() == ExecutionMode.INTERACTIVE.value:
            if candidate_payload.get("__SKILL_DONE__") is False:
                pending = extract_pending_interaction(
                    candidate_payload,
                    fallback_interaction_id=attempt_number,
                )
                if pending is None:
                    return _ResolvedBranch(
                        output_data={},
                        pending_interaction_candidate=None,
                        done_signal_found=False,
                        schema_errors=["target output validation error: pending interaction projection failed"],
                        branch_resolved=None,
                    )
                return _ResolvedBranch(
                    output_data={},
                    pending_interaction_candidate=pending,
                    done_signal_found=False,
                    schema_errors=[],
                    branch_resolved="pending",
                )
        output_data, done_signal_found = strip_done_marker_for_output_validation(candidate_payload)
        return _ResolvedBranch(
            output_data=output_data,
            pending_interaction_candidate=None,
            done_signal_found=done_signal_found,
            schema_errors=[],
            branch_resolved="final",
        )

    def _apply_result_file_fallback(
        self,
        *,
        skill: SkillManifest,
        run_dir: Path,
        execution_mode: str,
        attempt_number: int,
        current_errors: list[str],
        validation_warnings: list[str],
        extract_pending_interaction: Callable[..., dict[str, Any] | None],
    ) -> _FallbackResolution:
        fallback = resolve_result_file_fallback(skill=skill, run_dir=run_dir)
        for warning in fallback.warnings:
            if warning.code not in validation_warnings:
                validation_warnings.append(warning.code)
        if not isinstance(fallback.payload, dict):
            return _FallbackResolution(
                output_data={},
                has_structured_output=False,
                structured_output_source=None,
                done_signal_found=False,
                schema_output_errors=list(current_errors),
                pending_interaction_candidate=None,
                branch_resolved=None,
            )
        branch_resolved = "final"
        pending_interaction_candidate = None
        done_signal_found = True
        if (
            (execution_mode or "").strip().lower() == ExecutionMode.INTERACTIVE.value
            and fallback.payload.get("__SKILL_DONE__") is False
        ):
            pending_interaction_candidate = extract_pending_interaction(
                fallback.payload,
                fallback_interaction_id=attempt_number,
            )
            if pending_interaction_candidate is not None:
                branch_resolved = "pending"
                done_signal_found = False
        return _FallbackResolution(
            output_data={} if pending_interaction_candidate is not None else dict(fallback.payload),
            has_structured_output=True,
            structured_output_source="result_file_fallback",
            done_signal_found=done_signal_found,
            schema_output_errors=[],
            pending_interaction_candidate=pending_interaction_candidate,
            branch_resolved=branch_resolved,
        )

    def _build_repair_prompt(
        self,
        *,
        execution_mode: str,
        candidate: _CandidateResolution,
        schema_errors: list[str],
        prompt_summary: str,
    ) -> str:
        branch_line = (
            "For interactive mode, return exactly one JSON object that matches either the final branch "
            "(`__SKILL_DONE__ = true`) or the pending branch (`__SKILL_DONE__ = false` with `message` and `ui_hints`)."
            if (execution_mode or "").strip().lower() == ExecutionMode.INTERACTIVE.value
            else "Return exactly one final JSON object with `__SKILL_DONE__ = true`."
        )
        candidate_block = candidate.raw_candidate_preview or "No valid JSON object was extracted from the previous output."
        errors_block = "\n".join(f"- {item}" for item in schema_errors) if schema_errors else "- Unknown validation error"
        lines = [
            "Your previous output did not satisfy the Skill Runner output contract.",
            "",
            "Previous candidate:",
            candidate_block,
            "",
            "Validation errors:",
            errors_block,
            "",
            branch_line,
            "Do not output explanations.",
            "Do not output Markdown fences.",
        ]
        if prompt_summary.strip():
            lines.extend(
                [
                    "",
                    "Target output contract details:",
                    prompt_summary.strip(),
                ]
            )
        return "\n".join(lines).strip()

    def _default_errors_for_candidate(self, candidate: _CandidateResolution) -> list[str]:
        if not candidate.raw_candidate_present:
            return ["Output JSON missing or unreadable"]
        if candidate.deterministic_repair_applied and not candidate.deterministic_repair_succeeded:
            return ["Output JSON missing or unreadable"]
        return ["Target output validation failed"]

    def _sanitized_failure_reason(
        self,
        *,
        result: Any,
        auth_detection_high: bool,
    ) -> str | None:
        failure_reason = getattr(result, "failure_reason", None)
        if failure_reason == "AUTH_REQUIRED" and not auth_detection_high:
            return None
        return failure_reason

    def _build_legacy_candidate_projection(
        self,
        *,
        candidate_payload: dict[str, Any] | None,
        strip_done_marker_for_output_validation: Callable[[dict[str, Any]], tuple[dict[str, Any], bool]],
    ) -> tuple[dict[str, Any], bool, bool]:
        if not isinstance(candidate_payload, dict):
            return {}, False, False
        output_data, done_signal_found = strip_done_marker_for_output_validation(candidate_payload)
        return output_data, done_signal_found, True

    def _round_record(
        self,
        *,
        attempt_number: int,
        internal_round_index: int,
        candidate_source: str,
        validation_errors: list[str],
        prompt_summary: str,
        converged: bool,
        legacy_fallback_target: str | None,
        raw_candidate_present: bool,
        deterministic_repair_applied: bool,
        deterministic_repair_succeeded: bool,
        schema_valid: bool,
        branch_resolved: str | None,
        target_contract_mode: str,
        repair_level: str,
        resume_handle_reused: bool,
        outcome: str,
    ) -> dict[str, Any]:
        record = OutputRepairRoundRecord(
            attempt_number=attempt_number,
            internal_round_index=internal_round_index,
            repair_stage="schema_repair_rounds",
            candidate_source=candidate_source,
            executor="orchestrator.output_convergence_executor",
            validation_errors=list(validation_errors),
            repair_prompt_or_summary=prompt_summary[:4000],
            converged=converged,
            legacy_fallback_target=legacy_fallback_target,
            raw_candidate_present=raw_candidate_present,
            deterministic_repair_applied=deterministic_repair_applied,
            deterministic_repair_succeeded=deterministic_repair_succeeded,
            schema_valid=schema_valid,
            branch_resolved=branch_resolved,
            target_contract_mode=target_contract_mode,
            repair_level=repair_level,
            resume_handle_reused=resume_handle_reused,
            outcome=outcome,
        )
        return record.__dict__

    def _build_result(
        self,
        *,
        engine_result: Any,
        runtime_parse_result: dict[str, Any] | None,
        auth_detection_result: AuthDetectionResult,
        output_data: dict[str, Any],
        has_structured_output: bool,
        structured_output_source: str | None,
        done_signal_found: bool,
        schema_output_errors: list[str],
        repair_level: str,
        validation_warnings: list[str],
        pending_interaction_candidate: dict[str, Any] | None,
        convergence_state: str,
        legacy_fallback_target: str | None,
        process_exit_code: int | None,
        process_failure_reason: str | None,
        branch_resolved: str | None,
    ) -> OutputConvergenceResult:
        turn_payload_for_completion = dict(output_data) if output_data else {}
        return OutputConvergenceResult(
            output_data=dict(output_data),
            has_structured_output=has_structured_output,
            structured_output_source=structured_output_source,
            done_signal_found=done_signal_found,
            schema_output_errors=list(schema_output_errors),
            repair_level=repair_level or "none",
            validation_warnings=list(validation_warnings),
            pending_interaction_candidate=(
                dict(pending_interaction_candidate) if isinstance(pending_interaction_candidate, dict) else None
            ),
            convergence_state=convergence_state,
            legacy_fallback_target=legacy_fallback_target,
            process_exit_code=process_exit_code,
            process_failure_reason=process_failure_reason,
            auth_detection_result=auth_detection_result,
            branch_resolved=branch_resolved,
            turn_payload_for_completion=turn_payload_for_completion,
            runtime_parse_result=runtime_parse_result,
            engine_result=engine_result,
        )

    async def _run_adapter(
        self,
        *,
        adapter: Any,
        skill: SkillManifest,
        input_data: dict[str, Any],
        run_dir: Path,
        options: dict[str, Any],
        live_runtime_emitter: Any,
    ) -> Any:
        if self._adapter_accepts_live_runtime_emitter(adapter):
            return await adapter.run(
                skill,
                input_data,
                run_dir,
                options,
                live_runtime_emitter=live_runtime_emitter,
            )
        return await adapter.run(skill, input_data, run_dir, options)

    def _adapter_accepts_live_runtime_emitter(self, adapter: Any) -> bool:
        run_callable = getattr(adapter, "run", None)
        if run_callable is None:
            return False
        try:
            signature = inspect.signature(run_callable)
        except (TypeError, ValueError):
            return False
        for parameter in signature.parameters.values():
            if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                return True
            if parameter.name == "live_runtime_emitter":
                return True
        return False

    def _parse_runtime_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
    ) -> dict[str, Any] | None:
        try:
            return adapter.parse_runtime_stream(
                stdout_raw=raw_stdout.encode("utf-8", errors="replace"),
                stderr_raw=raw_stderr.encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
        except (
            AttributeError,
            LookupError,
            RuntimeError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return None

    def _parse_json_with_deterministic_repair(
        self,
        adapter: Any,
        text: str,
    ) -> tuple[dict[str, Any] | None, str]:
        parser = getattr(adapter, "parse_json_with_deterministic_repair", None)
        if callable(parser):
            parsed, repair_level = parser(text)
            if isinstance(parsed, dict):
                return parsed, repair_level or "none"
            return None, repair_level or "none"
        return None, "none"

    def _extract_candidate_text(
        self,
        *,
        runtime_parse_result: dict[str, Any] | None,
        raw_stdout: str,
    ) -> str:
        if isinstance(runtime_parse_result, dict):
            assistant_messages = runtime_parse_result.get("assistant_messages")
            if isinstance(assistant_messages, list):
                for item in reversed(assistant_messages):
                    if not isinstance(item, dict):
                        continue
                    text_obj = item.get("text")
                    if isinstance(text_obj, str) and text_obj.strip():
                        return text_obj.strip()
        return raw_stdout.strip()

    def _candidate_preview_from_payload(self, payload: dict[str, Any]) -> str:
        try:
            import json

            return json.dumps(payload, ensure_ascii=False, indent=2)[:500]
        except (TypeError, ValueError):
            return str(payload)[:500]


@dataclass(frozen=True)
class _ResolvedBranch:
    output_data: dict[str, Any]
    pending_interaction_candidate: dict[str, Any] | None
    done_signal_found: bool
    schema_errors: list[str]
    branch_resolved: str | None


@dataclass(frozen=True)
class _FallbackResolution:
    output_data: dict[str, Any]
    has_structured_output: bool
    structured_output_source: str | None
    done_signal_found: bool
    schema_output_errors: list[str]
    pending_interaction_candidate: dict[str, Any] | None
    branch_resolved: str | None


run_output_convergence_service = RunOutputConvergenceService()
