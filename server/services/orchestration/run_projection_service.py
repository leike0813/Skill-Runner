"""Backward-compatible shim to the new run_state_service."""

from server.services.orchestration.run_state_service import RunStateService, run_state_service


RunProjectionService = RunStateService
run_projection_service = run_state_service
