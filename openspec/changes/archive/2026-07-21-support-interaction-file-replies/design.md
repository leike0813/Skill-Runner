## Context

Skill Runner already exposes a canonical pending-interaction lifecycle: a reply is accepted atomically while a request is `waiting_user`, the pending record is consumed, `interaction.reply.accepted` is published, a resume ticket is created, and the request moves to `queued` before the next attempt becomes `running`. `upload_files` is present in the model and runtime schema, but two normalizers still downgrade it and no HTTP adapter accepts interaction files.

The existing reply row stores the private response used to resume the agent. That representation also reaches interaction history and attempt audit input today. A file continuation must contain a readable managed path, while public and diagnostic projections must never expose that path, a hash, raw multipart bytes, a temporary path, or an unsanitized filename.

## Goals / Non-Goals

**Goals:**

- Negotiate one opt-in file-reply capability with enforcement limits from one policy source.
- Validate multipart metadata and declared pending slots before accepting files.
- Publish files atomically into a request-owned workspace namespace and resume through the existing reply pipeline.
- Make repeated and concurrent submissions deterministic, durable, and single-resume.
- Provide a structured public file summary without exposing private continuation data.

**Non-Goals:**

- A second interaction state machine, new FCMP states, or new FCMP event names.
- Changes to the ordinary JSON reply wire contract or auth-import protocol.
- MIME/content inspection, malware scanning, or trust based on a client MIME declaration.
- Zotero Agents changes, release publication, version increments, or change archival.

## Decisions

### Capability and policy

`skillrunner.interaction-files.v1` is returned only when explicitly requested. Legacy default capability selection remains separate so an empty `requested_protocols` list has its existing response. Its payload is:

```json
{
  "supported": true,
  "max_files": 8,
  "max_file_bytes": 33554432,
  "max_total_bytes": 67108864
}
```

The three values come from one immutable policy resolved from server configuration. Configuration may lower but not exceed these protocol maxima and must be positive. Invalid configuration fails validation rather than being silently clamped. The handshake and upload service receive the same policy object. This avoids independent constants that can drift.

### Multipart adapter and strict DTOs

`POST /v1/jobs/{requestId}/interaction/reply/files` accepts exactly one UTF-8 JSON `metadata` part and one or more repeated `files` parts. The metadata part's declared content type is not trusted or required. Metadata, binding, private continuation, public summary, and internal receipt/manifest are explicit machine-readable DTOs with unknown fields forbidden.

The canonical slot key is `pending.ui_hints.files[].name`. A request must bind every uploaded file exactly once, cannot bind an index or slot twice, cannot omit a required slot, and cannot name an undeclared slot. `accept` remains a client-facing hint; spoofed MIME does not change acceptance. Empty files are rejected.

The router only parses multipart values, maps domain errors to HTTP responses, and calls the file service. Malformed JSON or multipart structure maps to 400, semantic DTO/binding/empty-file failures to 422, size/count limits to 413, missing requests to 404, stale/state/idempotency conflicts to 409, and storage failures to a safe 500 response.

### Managed workspace publication

Interaction files are continuation inputs, so they use the existing canonical `uploads/` root rather than a new workspace top-level directory. `RunWorkspaceLayout` owns this namespace:

`uploads/.interaction-replies/<request-namespace>/<interaction-id>/<receipt-token>/`

`.interaction-replies` is reserved for the server. Initial uploads may not occupy it. Every resolved path must remain inside the managed namespace; pre-existing files, symlinks, or directory conflicts are rejected. Display names are derived by splitting both POSIX and Windows separators, taking the basename, and removing unsafe control characters. Storage names are generated from an ordinal, random token, and safe suffix, never from a client path.

The service validates the pending interaction before reading bodies, then reads each `UploadFile` in bounded chunks while enforcing file and total limits and computing SHA-256. It writes into an exclusively created sibling temporary directory, writes an internal manifest, and atomically renames the directory to its final receipt directory. The continuation receives workspace-relative POSIX paths only.

The managed subtree is excluded from the run explorer, preview, debug bundles, and filesystem snapshots. The agent can still read it from the workspace-relative path supplied in the private continuation.

### Canonical acceptance and persistence

The file service constructs a private response:

```json
{
  "kind": "interaction_files",
  "message": "optional",
  "files": [
    {"slot": "paper", "name": "paper.pdf", "path": "uploads/.interaction-replies/...", "size_bytes": 12345}
  ]
}
```

It also constructs a public projection with the same `kind`, `message`, and file entries minus `path`. The existing interaction service remains the only owner of pending consumption, state transition, event publication, resume-ticket creation, and next-attempt scheduling. It is extended to accept private response, public projection, optional fingerprint, and optional receipt inputs; ordinary replies use existing defaults.

The successful HTTP receipt remains the existing `InteractionReplyResponse` with `status: "queued"`. The next attempt later transitions the request to `running` through the existing statechart.

### Idempotency and concurrency

The durable scope is `(request_id, interaction_id, idempotency_key)`. The canonical fingerprint hashes canonical JSON containing the interaction id, idempotency key, message, binding list in its original order, sanitized display names, file sizes, and each file SHA-256. Binding order and display name are intentionally significant because both affect continuation semantics.

Interaction persistence gains nullable private reply, public reply, fingerprint, and first receipt fields through an additive SQLite migration. Existing replies remain readable. A conditional transactional update and the existing interaction identity guarantee that only one submission consumes the pending interaction; process-local locking is only an optimization.

An existing idempotency key is checked before applying the normal current-state rejection so a replay can succeed after the run has left `waiting_user`. The new body is still streamed and hashed into a temporary directory. Matching fingerprints return the stored first receipt and delete the temporary directory; mismatches return 409. Concurrent losers delete only directories not referenced by the winning stored reply. Storage or promotion failure leaves the pending interaction unconsumed.

### Public and private observability

The private response is limited to the interaction reply record, resume ticket, and agent continuation. A single public-projection helper feeds:

- optional `response_summary` on the existing `interaction.reply.accepted` event;
- the existing safe string `response_preview`;
- interaction history and chat replay;
- attempt audit input and log previews.

The public file summary contains only `slot`, sanitized display `name`, and `size_bytes`. The internal manifest may contain SHA-256, managed relative paths, binding information, and the receipt token, but never raw bytes or unsanitized filenames. Absolute and temporary paths are never serialized.

## Risks / Trade-offs

- **Multipart parsing may spool a request before domain limits are evaluated** → use `UploadFile`, bounded chunk reads, configured HTTP/body protections, and immediate cleanup; never load entire files into memory.
- **A process can fail after atomic promotion but before reply acceptance** → use unique receipt directories and cleanup only when the stored winning reply does not reference them; orphan reconciliation can safely identify unreferenced receipt directories later.
- **Public summary fields expand an existing event payload** → make `response_summary` optional, keep `response_preview`, and leave event names/order and ordinary reply payloads unchanged.
- **Existing databases lack new receipt columns** → use nullable additive migration and retain the legacy comparison path for ordinary replies.
- **Shared physical workspaces can mix logical runs** → include the existing request namespace before interaction and receipt identifiers.
