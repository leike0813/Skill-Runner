## MODIFIED Requirements

### Requirement: Built-in E2E runtime options UI MUST follow context-aware visibility
E2E 客户端 runtime options 区域 MUST 仅暴露仍然有效的运行参数，不得继续展示已下线的 runtime debug 开关。

#### Scenario: runtime debug option is removed
- **WHEN** 用户查看 E2E run form 的 runtime options 区域
- **THEN** 页面 MUST NOT 显示 `debug` 相关 checkbox
- **AND** 表单提交 MUST NOT 发送 `runtime_options.debug`

### Requirement: 示例客户端 Run Observation MUST 提供 bundle 下载入口
示例客户端 MUST 继续提供普通 bundle 与 debug bundle 的独立下载入口，且该能力不依赖 runtime options 中的 debug 开关。

#### Scenario: debug bundle remains downloadable without runtime debug option
- **WHEN** 用户在 `/runs/{request_id}` 页面查看成功终态 run
- **THEN** 页面继续提供 `Download Bundle` 与 `Download Debug Bundle`
- **AND** 两个入口的可用性与 `runtime_options.debug` 无关
