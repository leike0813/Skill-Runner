## Context

Skill Runner installs the Zotero Bridge CLI, wrapper skill, and managed profile into runtime-owned cache paths during agent layout bootstrap. The installed runtime copies are already decoupled from run-local workspaces, but their source bundle is the built-in `plugins/zotero-bridge-cli-bundle` submodule. That makes the bundle version fixed by the service build.

The change keeps the current managed install boundary and replaces the default bundle source resolution with a managed cache source plus built-in fallback. The built-in submodule remains a valid offline seed. The managed cache lives under `SKILL_RUNNER_AGENT_CACHE_DIR`, which is already persistent in local and container deployments.

Configuration for the updater is project configuration and belongs in `server/config.py`. The deployment-derived `data/system_settings.json` remains scoped to UI-editable runtime settings and does not become the source of truth for this background updater.

## Goals / Non-Goals

**Goals:**
- Resolve Zotero Bridge CLI bundle from an active managed cache version when available.
- Automatically track the configured Git repository and branch in the background after service startup.
- Validate bundle structure and the current platform binary SHA256 before activation.
- Preserve service availability when update checks fail.
- Expose read-only diagnostics for the active source, active commit, and last update result.

**Non-Goals:**
- Add an administrator-triggered update endpoint or UI control.
- Store updater configuration in `data/system_settings.json`.
- Restart running agent subprocesses when a new bundle is activated.
- Replace the existing managed CLI/profile/wrapper install semantics.

## Decisions

### Managed cache first, built-in submodule fallback

Bundle resolution uses the managed store under:

```text
<SKILL_RUNNER_AGENT_CACHE_DIR>/plugin-bundles/zotero-bridge-cli-bundle
```

When that store has a valid active bundle, bootstrap reads from it. Otherwise bootstrap reads from `plugins/zotero-bridge-cli-bundle`.

Rationale: the cache path is writable and persistent after deployment, while the submodule path is image/release content. Keeping the submodule as fallback preserves first-start and offline behavior.

Alternative considered: replace the submodule path in-place with a mount or checkout. That couples updates to `/app/plugins` mutability and is weaker for container deployments where `/app` should remain image-owned.

### Project config in `server/config.py`

Updater defaults are defined under `config.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE`, including enabled flag, source repository, branch, interval, startup delay, and timeout.

Rationale: these values describe service behavior and deployment policy. They are not UI-editable runtime settings, so they should follow the existing project configuration pattern instead of the persisted system settings file.

Alternative considered: put the settings in `data/system_settings.json`. That would make a deployment-derived file a policy source for background update behavior and expand the current system settings contract beyond its UI-editable scope.

### Non-blocking background lifecycle

The FastAPI lifespan starts a background updater after core startup has initialized the runtime directories. The first check is delayed, then repeated at the configured interval. Shutdown cancels the loop.

Rationale: update checks need network and Git access, so they must not block API startup or container readiness. Existing installed/fallback bundle behavior remains available during checks.

Alternative considered: run update from container entrypoint before uvicorn. That would make startup sensitive to network failures and duplicate application-level runtime profile logic.

### Atomic activation after validation

The updater checks the remote branch HEAD, fetches content into staging, validates the bundle manifest, wrapper skill, profile template, and current platform binary hash, then activates the version by writing the current pointer and state.

Rationale: activation should only expose complete, validated bundles to bootstrap. Version directories keyed by commit make status and rollback reasoning straightforward.

Alternative considered: activate before installing the managed CLI, then repair on install failure. That risks making a bad bundle the default source for the next bootstrap.

### Read-only diagnostics

`skill-runnerctl doctor --json`, `preflight --json`, and `status --json` expose bundle status without triggering a network check.

Rationale: diagnostics should be safe and predictable in plugin-controlled flows. Update execution remains owned by the background manager.

Alternative considered: make `preflight` check for updates. That would turn a static readiness command into a networked mutation path.

## Risks / Trade-offs

- GitHub or network unavailable -> updater records failure and keeps the previous active bundle or built-in fallback.
- Upstream branch publishes an invalid bundle -> validation rejects it before activation.
- Git binary unavailable in a runtime image -> updater records failure; built-in fallback remains usable.
- New bundle is activated while runs are active -> only later subprocesses are guaranteed to see the new managed CLI/wrapper content.
- Cache volume is lost -> service falls back to the built-in submodule until the updater repopulates the managed store.

## Migration Plan

1. Ship the service with the built-in submodule unchanged as fallback.
2. On startup, bootstrap continues installing from the resolved bundle source.
3. The background updater populates the managed cache when it can reach the configured branch.
4. Operators can disable the updater through project configuration if a deployment requires frozen bundle behavior.
5. Rollback is performed by removing or correcting the managed active pointer/state; the runtime then falls back to the previous valid managed version or the built-in submodule.

## Open Questions

None.
