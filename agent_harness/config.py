from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from server.services.runtime_profile import RuntimeProfile, get_runtime_profile


HARNESS_RUN_ROOT_ENV = "SKILL_RUNNER_HARNESS_RUN_ROOT"


@dataclass(frozen=True)
class HarnessConfig:
    runtime_profile: RuntimeProfile
    run_root: Path
    project_root: Path | None = None


def resolve_harness_config() -> HarnessConfig:
    profile = get_runtime_profile()
    run_root_raw = os.environ.get(HARNESS_RUN_ROOT_ENV, "").strip()
    if run_root_raw:
        run_root = Path(run_root_raw).expanduser().resolve()
    else:
        run_root = (profile.data_dir / "harness_runs").resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    return HarnessConfig(
        runtime_profile=profile,
        run_root=run_root,
        project_root=Path.cwd().resolve(),
    )
