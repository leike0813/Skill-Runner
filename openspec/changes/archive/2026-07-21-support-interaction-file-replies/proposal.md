## Why

The pending-interaction protocol already models `upload_files`, but Skill Runner has no server endpoint that can turn selected files into a canonical interaction reply. The missing adapter prevents clients from completing file-backed interactions without bypassing the existing state machine and audit flow.

## What Changes

- Add a negotiated `skillrunner.interaction-files.v1` handshake capability whose advertised limits come from the same server policy used for upload enforcement.
- Add a multipart interaction reply endpoint accepting strict metadata plus repeated file parts.
- Store uploaded files in a request-owned managed workspace namespace and expose only safe workspace-relative paths to the resumed agent.
- Feed a typed file continuation into the existing canonical reply acceptance, event publication, and resume pipeline.
- Add durable upload fingerprints and receipts so idempotent replays cannot duplicate storage or resume a run twice.
- Separate private continuation data from public event, history, transcript, filesystem, bundle, and log projections.
- Preserve all existing FCMP states and event names, and preserve the ordinary JSON interaction reply contract.

## Capabilities

### New Capabilities

- `interaction-file-reply`: Multipart interaction file replies, upload policy, slot binding, managed storage, idempotency, concurrency, and privacy behavior.

### Modified Capabilities

- `zotero-agents-handshake`: Negotiate the interaction-file protocol and advertise its effective limits without changing legacy handshake responses.
- `interactive-job-api`: Route file replies through the existing pending-interaction acceptance and queued-resume lifecycle.
- `runtime-event-command-schema`: Define private file continuations and public safe file summaries in the machine-readable runtime contract.
- `run-file-contract`: Reserve and govern the request-owned workspace namespace used for interaction files.
- `run-audit-contract`: Prevent managed paths, hashes, raw filenames, and file bytes from leaking through public or diagnostic surfaces.

## Impact

- Adds one authenticated jobs API route and one opt-in handshake capability.
- Extends interaction/system DTOs, runtime schema definitions, workspace layout, SQLite interaction records, and orchestration services.
- Updates runtime sequence, file protocol, workspace reuse, API, handshake, stream, and audit documentation.
- Adds focused route, storage, idempotency, privacy, and end-to-end tests. No Zotero Agents code, release metadata, version number, dependency, FCMP state, or FCMP event-name change is included.
