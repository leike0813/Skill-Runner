## ADDED Requirements

### Requirement: The jobs API accepts multipart interaction file replies
The system MUST expose `POST /v1/jobs/{requestId}/interaction/reply/files` as an authenticated multipart adapter to the canonical interaction reply pipeline. The request MUST contain exactly one UTF-8 JSON `metadata` part and one or more repeated `files` parts, and the system MUST strictly validate the metadata and reject unknown fields.

#### Scenario: Valid multipart reply
- **WHEN** a client submits valid metadata and files for the current pending file interaction
- **THEN** the system accepts the reply through the canonical interaction pipeline and returns the existing interaction reply receipt with status `queued`

#### Scenario: Malformed multipart metadata
- **WHEN** the metadata part is missing, duplicated, not valid UTF-8 JSON, or contains unknown fields
- **THEN** the system rejects the request without consuming the pending interaction or publishing files

### Requirement: File bindings match the server-declared pending slots
The system MUST treat `pending.ui_hints.files[].name` as the canonical slot key and MUST validate bindings against the currently pending interaction rather than trusting the client declaration. Every uploaded file MUST be bound exactly once, each slot and file index MUST be unique, every required slot MUST be present, and every index MUST address an uploaded file.

#### Scenario: Complete valid binding set
- **WHEN** all uploaded files are uniquely bound to declared slots and every required slot is represented
- **THEN** the system continues file validation

#### Scenario: Invalid binding set
- **WHEN** a binding names an unknown or duplicate slot, repeats or exceeds a file index, omits a required slot, or leaves an uploaded file unbound
- **THEN** the system rejects the request without writing a final file directory or consuming the pending interaction

### Requirement: Upload limits come from one effective policy
The system MUST enforce positive effective limits for file count, per-file bytes, and aggregate bytes from the same immutable policy used by the handshake capability. The effective values MUST NOT exceed 8 files, 33,554,432 bytes per file, or 67,108,864 aggregate bytes.

#### Scenario: Upload exactly at a configured limit
- **WHEN** a valid request reaches but does not exceed each effective limit
- **THEN** the system accepts the file sizes

#### Scenario: Upload exceeds a configured limit
- **WHEN** file count, a streamed file, or the streamed aggregate exceeds its effective limit
- **THEN** the system stops processing, cleans temporary data, returns HTTP 413, and leaves the interaction pending

#### Scenario: Empty file
- **WHEN** any uploaded file contains zero bytes
- **THEN** the system rejects the request as semantically invalid and leaves the interaction pending

### Requirement: Interaction files are atomically published in a managed workspace namespace
The system MUST write interaction files in bounded chunks to an exclusively created sibling temporary directory under the request-owned `uploads/.interaction-replies/` namespace, calculate SHA-256 while writing, and atomically rename the completed directory to a collision-safe final receipt directory. The system MUST expose only workspace-relative POSIX paths to the continuation.

#### Scenario: Successful atomic publication
- **WHEN** every file and manifest is written and validated successfully
- **THEN** the system atomically publishes one final receipt directory before submitting the canonical reply

#### Scenario: Storage failure
- **WHEN** streaming, manifest creation, containment validation, or atomic publication fails
- **THEN** the system removes its temporary data and does not consume the pending interaction

### Requirement: Client filenames never control storage paths
The system MUST derive a sanitized display basename using both POSIX and Windows separators, generate collision-safe storage names independently, and reject absolute, traversing, symlinked, or otherwise non-contained storage targets. Client MIME and file extension declarations MUST NOT be treated as trusted content validation.

#### Scenario: Hostile client filename
- **WHEN** a multipart filename contains traversal, an absolute path, Windows separators, control characters, or duplicates another display name
- **THEN** the system stores the bytes only under generated contained names and exposes only sanitized display names

#### Scenario: Spoofed MIME
- **WHEN** a client MIME declaration differs from the filename or contents
- **THEN** the declaration does not bypass limits, containment, or slot validation and is not used as a security decision

### Requirement: File replies use canonical interaction acceptance
The system MUST submit the typed private file continuation through the existing interaction reply service. That service remains the only owner of pending consumption, `interaction.reply.accepted` publication, the `waiting_user` to `queued` transition, resume-ticket creation, and next-attempt scheduling.

#### Scenario: File reply is accepted once
- **WHEN** storage publication succeeds and the current interaction wins canonical acceptance
- **THEN** the pending interaction is consumed, one accepted event is emitted, one resume ticket is issued, and one next attempt is scheduled

#### Scenario: Stale or non-waiting interaction
- **WHEN** a non-replay request targets a stale interaction id or a request that is not `waiting_user`
- **THEN** the system applies the ordinary interaction reply conflict semantics and cleans any unreferenced uploaded directory

### Requirement: File reply idempotency is durable and content-sensitive
The system MUST scope idempotency to `(request_id, interaction_id, idempotency_key)` and persist a canonical fingerprint and first receipt with the accepted interaction. The fingerprint MUST include normalized metadata, original binding order, sanitized display names, file sizes, and each file SHA-256; binding order and display names MUST be significant.

#### Scenario: Matching replay after state advance
- **WHEN** the same scoped key is submitted with the same fingerprint after the request has advanced beyond `waiting_user`
- **THEN** the system returns the persisted first receipt, removes replay temporary data, and does not publish or resume again

#### Scenario: Conflicting replay
- **WHEN** the same scoped key is submitted with a different fingerprint
- **THEN** the system returns HTTP 409 without changing the accepted reply or run state

#### Scenario: Concurrent submissions
- **WHEN** two file replies race for the same pending interaction
- **THEN** a transactional conditional write allows exactly one canonical acceptance and each loser cleans only data not referenced by the winner

### Requirement: Private continuation and public file summaries are separate contracts
The private continuation MUST contain `kind`, optional `message`, and file entries with `slot`, sanitized display `name`, managed relative `path`, and `size_bytes`. Public events, history, transcript, API snapshots, filesystem snapshots, bundles, and log previews MUST use a safe projection that omits paths and hashes and contains only `kind`, optional `message`, and file `slot`, `name`, and `size_bytes`.

#### Scenario: Agent receives managed paths
- **WHEN** the next attempt is constructed from an accepted file reply
- **THEN** the agent continuation contains the managed workspace-relative paths required to read the files

#### Scenario: Public and diagnostic surfaces are inspected
- **WHEN** an accepted file reply is read through events, history, chat replay, run files, filesystem diffs, debug bundles, audit artifacts, or logs
- **THEN** no managed or absolute path, SHA-256, temporary directory, raw filename, or multipart bytes are exposed
