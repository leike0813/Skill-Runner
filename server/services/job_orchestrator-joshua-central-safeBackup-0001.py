import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from ..models import RunStatus, RunResponse
from ..services.workspace_manager import workspace_manager
from ..services.skill_registry import skill_registry
from ..adapters.codex_adapter import CodexAdapter
from ..adapters.gemini_adapter import GeminiAdapter
from ..services.schema_validator import schema_validator
from ..config import config

class JobOrchestrator:
    def __init__(self):
        # In v0, we just map engines to class instances
        self.adapters = {
            "codex": CodexAdapter(),
            "gemini": GeminiAdapter(),
        }

    async def run_job(self, run_id: str, skill_id: str, engine_name: str, options: Dict[str, Any]):
        """
        Background task to execute the skill.
        Updates status files in the workspace.
        """
        run_dir = workspace_manager.get_run_dir(run_id)
        if not run_dir:
            print(f"Error: Run dir {run_id} not found")
            return

        # 1. Update status to RUNNING
        self._update_status(run_dir, RunStatus.RUNNING)
        self._update_latest_run_id(run_id)

        try:
            # 2. Get Skill
            skill = skill_registry.get_skill(skill_id)
            if not skill:
                raise ValueError(f"Skill {skill_id} not found during execution")

            # 3. Get Adapter
            adapter = self.adapters.get(engine_name)
            if not adapter:
                raise ValueError(f"Engine {engine_name} not supported")

            # 4. Load Input
            with open(run_dir / "input.json", 'r') as f:
                input_data = json.load(f)

            # 4.1 Validate Input
            input_errors = schema_validator.validate_input(skill, input_data)
            if input_errors:
                raise ValueError(f"Input validation failed: {str(input_errors)}")

            # 5. Execute
            result = await adapter.run(skill, input_data, run_dir, options)

            # 6. Verify Result and Normalize
            warnings = []
            if result.exit_code == 0 and result.output_file_path and result.output_file_path.exists():
                try:
                    with open(result.output_file_path, "r") as f:
                        output_data = json.load(f)
                    output_warnings = schema_validator.validate_output(skill, output_data)
                    warnings.extend(output_warnings)
                except Exception as e:
                    warnings.append(f"Failed to validate output schema: {str(e)}")

            # 7. Update status to SUCCEEDED (or FAILED if exit_code != 0)
            final_status = RunStatus.SUCCEEDED if result.exit_code == 0 else RunStatus.FAILED
            self._update_status(
                run_dir, 
                final_status, 
                error=None if result.exit_code == 0 else {"message": f"Exit code {result.exit_code}", "stderr": result.raw_stderr},
                warnings=warnings
            )

        except Exception as e:
            print(f"Job failed: {e}")
            self._update_status(run_dir, RunStatus.FAILED, error={"message": str(e)})

    def _update_status(self, run_dir: Path, status: RunStatus, error: Optional[Dict] = None, warnings: List[str] = []):
        # In v0, we might just rely on checking result/ but let's write a status file
        # This mirrors what WorkspaceManager does but updates it
        # Ideally WorkspaceManager should own this writing logic
        # For simplicity, I'll write a simple status.json sidecar
        
        status_data = {
            "status": status,
            "updated_at": str(datetime.now()),
            "error": error,
            "warnings": warnings
        }
        with open(run_dir / "status.json", "w") as f:
            json.dump(status_data, f)

    def _update_latest_run_id(self, run_id: str):
        """Updates the latest_run_id file in the runs directory."""
        runs_dir = config.RUNS_DIR
        try:
            with open(runs_dir / "latest_run_id", "w") as f:
                f.write(run_id)
        except Exception as e:
            print(f"Failed to update latest_run_id: {e}")

job_orchestrator = JobOrchestrator()

# Helper imports for inside async method
import json
from datetime import datetime
from typing import List
