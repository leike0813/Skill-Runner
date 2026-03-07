## ADDED Requirements

### Requirement: 示例客户端 Run Observation MUST 提供 bundle 下载入口
示例客户端 MUST 在 Run Observation 页面提供可直接下载当前 run bundle 的入口，避免用户离开 E2E 页面进行二次操作。

#### Scenario: user downloads run bundle from observation page
- **WHEN** 用户在 `/runs/{request_id}` 页面点击下载 bundle
- **THEN** 浏览器开始下载 zip 文件
- **AND** 下载目标对应当前 run 的 bundle 内容

#### Scenario: download action does not break file explorer
- **WHEN** 用户触发 bundle 下载
- **THEN** 文件树与文件预览功能继续可用
- **AND** 页面不会被强制跳转到非 observation 页面
