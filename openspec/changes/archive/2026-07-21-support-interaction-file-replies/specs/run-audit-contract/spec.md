## ADDED Requirements

### Requirement: Interaction file manifests MUST remain internal and request-owned
The system MUST store any interaction file manifest within the managed request namespace. The manifest MAY contain SHA-256, fingerprint inputs, receipt identity, bindings, and managed relative paths, but MUST NOT contain raw multipart bytes or unsanitized client filenames.

#### Scenario: Internal manifest is written
- **WHEN** an interaction file directory is successfully prepared
- **THEN** its manifest is stored with request ownership and is excluded from public file and audit surfaces

### Requirement: Interaction file observability MUST use a privacy-safe projection
Events, interaction history, transcript/chat replay, API snapshots, log previews, and attempt audit input MUST use a shared public file summary containing only `kind`, optional `message`, and file `slot`, sanitized display `name`, and `size_bytes`. They MUST NOT serialize the private continuation.

#### Scenario: Accepted file reply is audited
- **WHEN** `interaction.reply.accepted` and related history or audit artifacts are produced
- **THEN** they contain a safe preview and optional structured public summary
- **AND** they do not contain managed or absolute paths, SHA-256, temporary directories, raw filenames, or file bytes

#### Scenario: File upload fails before acceptance
- **WHEN** validation, streaming, storage, or canonical acceptance fails
- **THEN** no accepted audit event is written and temporary data is cleaned best-effort

### Requirement: Managed interaction file storage MUST be hidden from diagnostic file surfaces
The run explorer, file preview, debug bundle, and filesystem snapshot MUST exclude `uploads/.interaction-replies/` and its descendants so private paths and hashes cannot be rediscovered indirectly.

#### Scenario: Diagnostic surfaces enumerate a run
- **WHEN** a run containing managed interaction files is inspected through file listing, preview, bundle, or filesystem-diff APIs
- **THEN** the reserved interaction-reply subtree and its manifest do not appear
