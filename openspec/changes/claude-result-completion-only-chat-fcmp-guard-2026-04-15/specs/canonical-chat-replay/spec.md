## ADDED Requirements

### Requirement: chat replay publication MUST be FCMP-derived and MUST NOT shortcut parser semantics

canonical chat replay MUST 只消费已提交的 FCMP 行；parser emission、engine parser helper、
或 live semantic 快捷路径 MUST NOT 直接写入 chat。

#### Scenario: assistant chat row is published from committed FCMP row

- **GIVEN** runtime 即将发布一条 assistant 相关 chat replay
- **WHEN** chat replay publisher 被调用
- **THEN** 输入 MUST 是已经通过 schema 校验并写入 live FCMP journal 的 FCMP row
- **AND** 该 row MUST 已经拥有稳定的 `seq`

#### Scenario: parser emission cannot bypass the runtime event lane

- **GIVEN** parser 识别出 assistant message 或 completion 语义
- **WHEN** 系统将其对外暴露为 chat
- **THEN** 该语义 MUST 先被发布为 runtime event / FCMP event
- **AND** chat replay MUST NOT 从 parser emission 直接生成条目
