from __future__ import annotations

import logging
from datetime import datetime

from .run_attempt_projection_finalizer import RunAttemptFinalizeInput

logger = logging.getLogger(__name__)


class RunAttemptAuditFinalizer:
    def finalize(
        self,
        *,
        inputs: RunAttemptFinalizeInput,
        finished_at: datetime,
    ) -> None:
        try:
            inputs.audit_service.write_attempt_audit_artifacts(
                run_dir=inputs.context.run_dir,
                run_id=inputs.run_id,
                request_id=inputs.request_id,
                engine_name=inputs.context.request.engine_name,
                execution_mode=inputs.execution_mode,
                attempt_number=inputs.context.attempt_number,
                started_at=inputs.attempt_started_at,
                finished_at=finished_at,
                status=inputs.outcome.final_status,
                fs_before_snapshot=inputs.fs_before_snapshot,
                process_exit_code=inputs.outcome.process_exit_code,
                process_failure_reason=inputs.outcome.process_failure_reason,
                process_raw_stdout=inputs.outcome.process_raw_stdout,
                process_raw_stderr=inputs.outcome.process_raw_stderr,
                adapter=inputs.adapter if inputs.adapter is not None else inputs.context.adapter,
                turn_payload=inputs.outcome.turn_payload_for_completion,
                validation_warnings=inputs.outcome.warnings,
                terminal_error_code=inputs.outcome.final_error_code,
                options=inputs.options,
                success_source=inputs.outcome.success_source,
                auth_detection=inputs.outcome.auth_detection_result.as_dict(),
                auth_session=inputs.outcome.auth_session_meta,
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            logger.warning(
                "Failed to write attempt audit artifacts for run_id=%s attempt=%s",
                inputs.run_id,
                inputs.context.attempt_number,
                exc_info=True,
            )
