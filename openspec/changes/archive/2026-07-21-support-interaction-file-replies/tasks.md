## 1. Contracts and documentation

- [x] 1.1 Sync all delta requirements into the main OpenSpec capabilities and add the new `interaction-file-reply` main spec.
- [x] 1.2 Extend the runtime JSON Schema with strict file metadata, binding, private continuation, public summary, receipt, and manifest contracts.
- [x] 1.3 Update API, Zotero integration, runtime sequence/stream/schema, file protocol, and workspace reuse documentation.

## 2. Capability and transport models

- [x] 2.1 Add the shared interaction-file policy, configuration validation, handshake capability constant, and opt-in advertised limits.
- [x] 2.2 Add strict interaction file DTOs and export them through the model boundary.
- [x] 2.3 Add the multipart jobs route with stable error mapping and no orchestration logic.

## 3. Storage and canonical acceptance

- [x] 3.1 Add the request-owned managed interaction-files workspace layout, reserved-path enforcement, atomic publication, manifest, and cleanup service.
- [x] 3.2 Extend interaction persistence with additive fingerprint, receipt, and public projection fields plus transactional replay/concurrency behavior.
- [x] 3.3 Extend the canonical interaction service to accept private/public projections without duplicating state transitions, event publication, or resume scheduling.
- [x] 3.4 Preserve `upload_files` in lifecycle and engine-adapter normalization.

## 4. Privacy boundaries

- [x] 4.1 Use the public projection for accepted-event summary, history, chat replay, and audit input while retaining private paths only for agent continuation.
- [x] 4.2 Exclude the managed interaction-reply subtree from filesystem snapshots, run explorer, preview, and debug bundles.

## 5. Verification

- [x] 5.1 Add or extend focused handshake, multipart, file-service, store, deduplication, normalization, schema, filtering, and integration tests.
- [x] 5.2 Run OpenSpec strict validation, focused tests, required runtime gates, deduplication tests, an in-process real multipart smoke test, and `git diff --check`.
