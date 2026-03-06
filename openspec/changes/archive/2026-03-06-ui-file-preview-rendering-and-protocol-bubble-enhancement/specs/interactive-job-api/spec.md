## ADDED Requirements

### Requirement: 文件预览响应 MUST 支持格式化扩展字段
文件预览接口 MUST 在保持现有字段兼容的基础上，提供格式化渲染辅助字段。

#### Scenario: 返回扩展字段
- **WHEN** 客户端请求文件预览
- **THEN** 响应包含既有字段 `mode/content/size/meta`
- **AND** 响应可包含 `detected_format`、`rendered_html`、`json_pretty`

### Requirement: E2E Run 文件预览 MUST 可滚动并按格式渲染
E2E Run 页文件预览 MUST 支持长内容滚动，并根据预览格式渲染 Markdown / JSON。

#### Scenario: 长内容文件
- **WHEN** 预览内容超出容器高度
- **THEN** 用户可在预览面板内纵向滚动

#### Scenario: Markdown / JSON 文件
- **WHEN** 预览结果包含 `detected_format = markdown|json`
- **THEN** 前端使用对应渲染分支展示内容
- **AND** 非 markdown/json 保持文本分支
