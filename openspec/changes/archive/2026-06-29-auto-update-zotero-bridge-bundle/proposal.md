# Change: Auto-update Zotero Bridge CLI bundle

## Summary

Allow deployed Skill Runner services to update the managed Zotero Bridge CLI bundle after deployment by tracking the `host-bridge/zotero-bridge-cli-bundle` branch of `https://github.com/leike0813/zotero-agents`.

## Motivation

The current bundle source is the in-repository submodule under `plugins/zotero-bridge-cli-bundle`. That makes the bundled CLI and wrapper skill fixed at service build/release time. When the Zotero Bridge bundle changes, operators must update and redeploy the whole service even though the runtime already installs the CLI and wrapper skill into managed cache paths.

## Scope

- Add project-level auto-update configuration in `server/config.py`.
- Add a managed bundle store under the agent cache.
- Resolve bundle source from managed store first, then fallback to the built-in submodule.
- Start a non-blocking background updater from application lifecycle.
- Expose read-only update status through local diagnostic commands.
- Keep the existing managed CLI/profile/wrapper install behavior.

## Non-goals

- No administrator-triggered update API.
- No runtime UI settings or `data/system_settings.json` schema changes.
- No interruption or restart of currently running agent subprocesses.
