## ADDED Requirements

### Requirement: E2E run timestamps MUST be rendered from timezone-explicit values
E2E runs 列表与 run observation 页面 MUST 使用带时区语义的时间值，以保证浏览器本地时区展示正确。

#### Scenario: e2e runs list uses timezone-explicit updated_at
- **WHEN** 用户访问 `/runs`
- **THEN** 列表中的 `updated_at` 使用带明确时区语义的时间值渲染
- **AND** 浏览器本地时区转换后不产生 UTC/本地混淆

### Requirement: E2E file preview MUST consume unified line-numbered rendered html
E2E Observation 文件预览 MUST 优先消费后端统一生成的 `rendered_html`，并在除 Markdown 外的可显示文本预览中显示行号。

#### Scenario: preview jsonl file in e2e observation
- **WHEN** 用户在 Observation 页面打开 `.jsonl` 文件
- **THEN** 页面显示 JSONL 语义渲染内容
- **AND** 行号与后端预览结果保持一致

#### Scenario: markdown preview stays rich-text only
- **WHEN** 用户打开 Markdown 文件
- **THEN** 页面显示富文本 Markdown
- **AND** 不额外追加源码行号栏
