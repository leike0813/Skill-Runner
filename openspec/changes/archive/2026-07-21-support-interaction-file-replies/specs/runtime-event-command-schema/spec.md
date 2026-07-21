## MODIFIED Requirements

### Requirement: orchestrator schema MUST 识别 interaction.reply.accepted
runtime protocol schema MUST 将 `interaction.reply.accepted` 视为一等 orchestrator event，并校验其稳定的 reply-acceptance 元数据。事件 MUST 保留 `response_preview`，并且 MAY 为文件回复增加不含私有路径或哈希的结构化 `response_summary`。

#### Scenario: reply-accepted orchestrator event 校验成功
- **WHEN** 后端输出一条类型为 `interaction.reply.accepted` 的 orchestrator event
- **THEN** schema 校验 MUST 接受包含 `interaction_id`、`accepted_at` 和 `response_preview` 的 payload
- **AND** 下游协议翻译 MAY 依赖这些字段，而无需绕过 schema 校验

#### Scenario: file reply accepted event uses safe projection
- **WHEN** 被接受的 interaction reply 是 `interaction_files`
- **THEN** `response_preview` MUST 由公开安全摘要生成
- **AND** 可选 `response_summary.files` MUST 仅包含 `slot`、清理后的 display `name` 与 `size_bytes`
- **AND** payload MUST NOT 包含 managed path、absolute path、SHA-256、temporary path 或 file bytes

## ADDED Requirements

### Requirement: Runtime schema MUST distinguish private file continuation from public summary
The runtime schema MUST define strict machine-readable types for multipart metadata, file bindings, private `interaction_files` continuation, public file summary, and internal fingerprint/receipt/manifest records. The private continuation MAY contain managed relative paths; the public summary MUST NOT.

#### Scenario: Private continuation validates
- **WHEN** a canonical resume command contains an `interaction_files` response with `slot`, sanitized `name`, managed relative `path`, and `size_bytes`
- **THEN** the runtime schema accepts it as a private continuation response

#### Scenario: Public summary validates
- **WHEN** history or an accepted event contains a structured file response summary
- **THEN** the runtime schema accepts only `kind`, optional `message`, and file `slot`, `name`, and `size_bytes`

### Requirement: Public replay surfaces MUST NOT serialize private continuation data
Writers of interaction history, chat replay, events, API snapshots, and log previews MUST project file replies through the public summary type rather than serializing the private continuation. Ordinary JSON reply and historical read behavior MUST remain compatible.

#### Scenario: File reply is written to history
- **WHEN** an accepted file reply is persisted or rebuilt for a public replay surface
- **THEN** the output contains a safe structured summary and optional safe preview without managed paths or hashes
