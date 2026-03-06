## MODIFIED Requirements

### Requirement: 文件预览响应 MUST 支持格式化扩展字段
文件预览接口 MUST 在保持现有核心字段兼容的前提下，支持更丰富的文本格式识别与渲染增强。

#### Scenario: 扩展格式识别
- **WHEN** 客户端请求文件预览
- **THEN** 系统可识别 `json|yaml|toml|python|javascript|markdown|text`
- **AND** 返回结果保持原有字段兼容

#### Scenario: 渲染失败回退
- **WHEN** 某格式高亮渲染失败或依赖不可用
- **THEN** 接口返回普通文本预览
- **AND** 客户端仍可无中断展示内容
