# Design

## Decision

Adopt a fixed non-root runtime user inside the official container image and make that the default compose/runtime posture. Do not add a Claude-specific root fallback such as environment-variable spoofing or permission-mode downgrades.

## Key Decisions

### 1) Build as root, run as non-root

- Image build steps remain root-owned for package install, venv creation, and binary bootstrap.
- Final image runtime switches to a fixed `skillrunner` user.
- Runtime-writable directories are pre-created and chowned during build so entrypoint scripts can continue to work unchanged under non-root.

### 2) Optional bind mounts remain operator-managed

- `./skills:/app/skills` remains the default host bind mount and only requires host-side readability.
- `./data:/data` remains optional and is not auto-managed by the image.
- Compose and docs must explicitly say that if `./data:/data` is enabled, the host directory must be writable by the non-root container user.
- A permissive fallback such as `chmod 777 ./data` is acceptable documentation guidance for local/debug deployments, but it is not formalized as a product-side permission orchestration feature.

### 3) Claude compatibility is solved at deployment posture, not engine logic

- Claude headless run keeps `permissions.defaultMode = "bypassPermissions"`.
- Container support for Claude now depends on the image defaulting to non-root execution.
- If operators override the runtime user back to root, that deployment is outside the supported default posture.

## Affected Specs

- `local-deploy-bootstrap`
  - add container default non-root runtime requirement
  - add optional `./data` bind mount permission guidance requirement
- `runtime-environment-parity`
  - require container runtime defaults to avoid root-only assumptions
  - require managed runtime paths to remain writable without system-level root escalation

## Implementation Notes

- The Docker image should create a fixed runtime user and switch to `USER <name>` at the end.
- `/data`, `/opt/cache`, `/app`, and runtime-home paths must be writable by that user before entrypoint handoff.
- Documentation changes should be limited to supported deployment posture and optional bind-mount caveats; no protocol or API text should suggest a new HTTP behavior.
