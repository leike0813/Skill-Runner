from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from server.models import AttemptAuditMeta, RunAuditContract


class RunAuditContractService:
    """Initializes the canonical .audit skeleton for each attempt."""

    def _contract(self, run_dir: Path, attempt_number: int) -> RunAuditContract:
        audit_dir = run_dir / ".audit"
        return RunAuditContract(
            request_id="",
            run_id=run_dir.name,
            attempt_number=attempt_number,
            request_input_path=str(audit_dir / "request_input.json"),
            run_service_log_path=str(audit_dir / "service.run.log"),
            meta_path=str(audit_dir / f"meta.{attempt_number}.json"),
            orchestrator_events_path=str(audit_dir / f"orchestrator_events.{attempt_number}.jsonl"),
            events_path=str(audit_dir / f"events.{attempt_number}.jsonl"),
            fcmp_events_path=str(audit_dir / f"fcmp_events.{attempt_number}.jsonl"),
            service_log_path=str(audit_dir / f"service.{attempt_number}.log"),
            stdin_path=str(audit_dir / f"stdin.{attempt_number}.log"),
            stdout_path=str(audit_dir / f"stdout.{attempt_number}.log"),
            stderr_path=str(audit_dir / f"stderr.{attempt_number}.log"),
            pty_output_path=str(audit_dir / f"pty-output.{attempt_number}.log"),
            fs_before_path=str(audit_dir / f"fs-before.{attempt_number}.json"),
            fs_after_path=str(audit_dir / f"fs-after.{attempt_number}.json"),
            fs_diff_path=str(audit_dir / f"fs-diff.{attempt_number}.json"),
            parser_diagnostics_path=str(audit_dir / f"parser_diagnostics.{attempt_number}.jsonl"),
            protocol_metrics_path=str(audit_dir / f"protocol_metrics.{attempt_number}.json"),
        )

    def write_request_input_snapshot(
        self,
        *,
        run_dir: Path,
        request_payload: dict[str, object],
    ) -> Path:
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        path = audit_dir / "request_input.json"
        path.write_text(
            json.dumps(request_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def initialize_run_audit(
        self,
        *,
        run_dir: Path,
    ) -> None:
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        run_service_log_path = audit_dir / "service.run.log"
        if not run_service_log_path.exists():
            run_service_log_path.write_text("", encoding="utf-8")

    def initialize_attempt_audit(
        self,
        *,
        run_dir: Path,
        request_id: str,
        attempt_number: int,
        status: str,
        engine: str | None = None,
        skill_id: str | None = None,
    ) -> None:
        contract = self._contract(run_dir, attempt_number)
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        meta = AttemptAuditMeta(
            request_id=request_id,
            run_id=run_dir.name,
            attempt_number=attempt_number,
            created_at=datetime.utcnow(),
            status=status,
            engine=engine,
            skill_id=skill_id,
        )
        meta_path = Path(contract.meta_path)
        if not meta_path.exists():
            meta_path.write_text(json.dumps(meta.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")

        attempt_paths = [
            contract.run_service_log_path,
            contract.orchestrator_events_path,
            contract.events_path,
            contract.fcmp_events_path,
            contract.service_log_path,
            contract.stdin_path,
            contract.stdout_path,
            contract.stderr_path,
            contract.pty_output_path,
            contract.fs_before_path,
            contract.fs_after_path,
            contract.fs_diff_path,
            contract.parser_diagnostics_path,
        ]
        for file_path in attempt_paths:
            if not file_path:
                continue
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("", encoding="utf-8")

        protocol_metrics_path = Path(contract.protocol_metrics_path)
        if not protocol_metrics_path.exists():
            protocol_metrics_path.write_text(
                json.dumps(
                    {
                        "attempt_number": attempt_number,
                        "created_at": datetime.utcnow().isoformat(),
                        "event_count": 0,
                        "diagnostic_count": 0,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )


run_audit_contract_service = RunAuditContractService()
