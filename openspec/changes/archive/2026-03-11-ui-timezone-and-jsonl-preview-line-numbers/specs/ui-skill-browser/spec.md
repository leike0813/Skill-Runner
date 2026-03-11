## ADDED Requirements

### Requirement: Skill Browser file preview MUST support jsonl and line-numbered text rendering
Skill Browser 文件预览 MUST 支持 `.jsonl` 预览，并且除 Markdown 外的可显示文本文件 MUST 显示行号。

#### Scenario: skill browser previews jsonl file
- **WHEN** 用户在 Skill Browser 中打开 `.jsonl` 文件
- **THEN** 页面以 JSONL 语义渲染文件内容
- **AND** 显示稳定的文本行号

#### Scenario: plain text preview includes line numbers
- **WHEN** 用户在 Skill Browser 中打开普通文本文件
- **THEN** 页面显示文件内容
- **AND** 行号与文本内容同时可见

#### Scenario: markdown preview remains rich-text
- **WHEN** 用户在 Skill Browser 中打开 Markdown 文件
- **THEN** 页面继续显示富文本结果
- **AND** 不切换为源码行号模式
