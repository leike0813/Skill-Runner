## ADDED Requirements

### Requirement: Live parser emission order MUST define canonical RASP order
系统 MUST 将 live parser session 的 emission 顺序定义为 canonical RASP 顺序；audit mirror、batch backfill 和 replay 路径 MUST NOT 改写该顺序。

#### Scenario: parser emission order becomes rasp_seq order
- **WHEN** `LiveStreamParserSession.feed()` 或 `finish()` 产出多条 emission
- **THEN** 这些 emission 派生的 RASP MUST 按产出顺序获得 `rasp_seq`
- **AND** 后续 mirror/replay MUST 保持这一顺序

### Requirement: Parser-originated FCMP MUST be produced as candidates before publication
系统 MUST 先把 parser-originated FCMP 构造成 candidate，再交给顺序 gate 决定是否发布。

#### Scenario: parser does not publish FCMP directly
- **WHEN** parser 识别出 assistant 或 diagnostic 语义
- **THEN** 它 MUST 先产出可被 gate 消费的 candidate
- **AND** MUST NOT 直接绕过 gate 发布 FCMP

### Requirement: Parser-originated FCMP MUST derive from incremental emissions without retroactive reordering
系统 MUST 从 parser 的增量 emission 派生 parser-originated FCMP，且 MUST NOT 允许事后 batch rebuild 重新定义它们在 active run 中的相对顺序。

#### Scenario: live parser FCMP is not overwritten by batch backfill
- **WHEN** parser live session 已发布某条 assistant 或 diagnostic FCMP
- **THEN** batch parse/backfill MAY 作为 parity 或 fallback 使用
- **AND** MUST NOT 覆盖该 FCMP 在 active timeline 中的相对顺序

### Requirement: Live parser emissions MUST expose stable correlation anchors
系统 MUST 要求 live parser emission 为派生的 FCMP/RASP 提供稳定的关联锚点，以支撑跨流因果回溯。

#### Scenario: FCMP and RASP share publish correlation
- **WHEN** 同一 parser emission 同时派生出 FCMP 和 RASP
- **THEN** 两者 MUST 共享稳定的 `publish_id`
- **AND** 后续依赖事件 MAY 通过 `caused_by.publish_id` 建立因果关系
