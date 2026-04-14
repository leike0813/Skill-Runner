## Why

Codex headless execution previously used `LANDLOCK_ENABLED=0` as the only signal for downgrading
from `--full-auto` to `--yolo`. That was too weak for real deployments where `bubblewrap` is
installed but unusable at runtime. In the observed failure mode, `bwrap` existed, but the smallest
smoke test failed during uid-map setup with `Permission denied`, while the generated Codex profile
still forced `sandbox_mode = "workspace-write"`. The result was an ineffective partial fallback:
CLI intent changed in some cases, but the generated runtime config still triggered the failing
sandbox path.

This change formalizes the fix already implemented in code: Codex headless execution now uses a
runtime sandbox probe and only keeps sandboxed auto mode when the probe is truly available.

## What Changes

- Add a Codex-specific sandbox runtime probe and persisted probe sidecar under `agent_home/.codex/`.
- Upgrade Codex sandbox status collection from environment-only heuristics to real runtime probe
  results.
- Require Codex headless start/resume command construction to use the same probe result when
  choosing between `--full-auto` and `--yolo`.
- Require Codex headless config composition to apply a runtime-only sandbox override to
  `sandbox_mode = "danger-full-access"` whenever the probe is unavailable.
- Keep the static repository default in `server/engines/codex/config/enforced.toml` unchanged.

## Capabilities

### Modified Capabilities

- `interactive-engine-turn-protocol`: Codex headless command defaults now depend on runtime sandbox
  availability rather than only on `LANDLOCK_ENABLED`.
- `engine-adapter-runtime-contract`: Codex headless runtime now includes a persisted sandbox probe,
  runtime-unavailable detection, and an effective dual fallback covering both CLI flags and
  generated config.

## Impact

- Affected code: `AgentCliManager`, Codex sandbox probe helpers, Codex command builder, Codex
  execution adapter, and Codex config composer.
- Affected tests: agent CLI manager, adapter command profile, and Codex adapter headless command /
  config composition regressions.
- Public HTTP API, FCMP, RASP, `PendingInteraction`, and Codex UI shell launch policy remain
  unchanged.
