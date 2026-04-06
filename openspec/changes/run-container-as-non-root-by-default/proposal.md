## Why

Claude headless runs currently rely on `bypassPermissions`, but Claude Code rejects that mode under `root/sudo` in non-sandboxed launches. Our default container image and compose stack still ran as root, so the default deployment posture could fail even when the runtime image already included the expected sandbox dependencies.

## What Changes

- Change the default container runtime posture from root to a fixed non-root user.
- Clarify that optional `./data:/data` bind mounts are operator-managed and must be writable by the container runtime user.
- Keep Claude headless run configuration unchanged; solve the incompatibility through deployment posture instead of engine-specific root fallbacks.
- Update container and API docs so the supported Claude container path is explicitly “non-root by default”.

## Capabilities

### New Capabilities

### Modified Capabilities
- `local-deploy-bootstrap`: Container deployment defaults must document and enforce a non-root runtime posture, including optional bind-mount permission guidance.
- `runtime-environment-parity`: The container runtime profile must no longer assume root execution and must keep managed runtime paths writable under a non-root user.

## Impact

- Affected systems: `Dockerfile`, `docker-compose.yml`, container entrypoints, deployment docs.
- No public HTTP API changes.
- Operators who enable `./data:/data` bind mounts must ensure host-side write permissions for the container user.
