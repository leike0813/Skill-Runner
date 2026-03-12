## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks and delta specs for this change.

## 2. Local Lease Lifecycle APIs

- [x] 2.1 Add `/v1/local-runtime/status` and lease acquire/heartbeat/release APIs.
- [x] 2.2 Add local lease TTL sweep and self-shutdown trigger for local mode.
- [x] 2.3 Ensure pytest execution does not terminate process on lease-triggered shutdown.

## 3. Plugin Control CLI

- [x] 3.1 Add `scripts/skill_runnerctl.py` with `install/up/down/status/doctor`.
- [x] 3.2 Add shell/PowerShell wrappers for `skill-runnerctl`.
- [x] 3.3 Add Docker mode status/start/stop control path.

## 4. Installers and Deploy Script Alignment

- [x] 4.1 Add `skill-runner-install.sh` and `skill-runner-install.ps1` (release + SHA256 verify).
- [x] 4.2 Keep `deploy_local.*` as implementation path and switch default bind to localhost.
- [x] 4.3 Remove hard blocking on optional ttyd dependency in local deploy.
- [x] 4.4 Update tag release workflow to publish installer source package + checksum (with submodules).

## 5. Docs and Validation

- [x] 5.1 Update API/reference/deploy docs and add Zotero plugin integration contract.
- [x] 5.2 Add/adjust route-level tests for local runtime lease API.
