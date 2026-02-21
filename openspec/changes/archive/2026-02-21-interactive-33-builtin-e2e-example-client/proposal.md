## Why

当前 E2E 验证主要依赖接口级调用，缺少“真实客户端行为”这一层，导致输入组装、文件上传、交互式 reply、结果呈现等前端链路难以稳定回归。需要提供一个内建的示例客户端服务，用于在同仓内复现真实用户操作路径并支撑 E2E 测试。

## What Changes

- 新增一套内建 E2E 示例客户端服务，独立进程与独立端口运行。
- 示例客户端默认端口为 `8011`，并支持通过环境变量覆盖，未配置时回退到 `8011`。
- 示例客户端采用内建 UI 同技术栈（服务端模板 + htmx + 原生 JavaScript）实现。
- 新增“技能选择 -> 输入填写/文件上传 -> 提交执行 -> 交互式对话 -> 结果展示”的完整用户流。
- 客户端连接后端后自动读取可用 Skill、描述与输入/参数规格，并按规格动态渲染执行表单。
- 客户端在提交前执行输入校验，模拟前端打包请求并调用后端执行接口。
- 客户端支持运行期观测（状态、stdout/stderr、pending/reply）直到终态，并在终态解包并展示结果与产物。
- 客户端新增“Runs”入口：每个在客户端创建过的 run 都可从 UI 再次进入实时观测与对话页面。
- 录制回放定位为实时观测页的子功能入口，不再作为唯一可重新进入 run 的入口。
- 结果页中的文件树与文件预览交互复用内建管理 UI 的 run 观测页面实现样式与交互模式。
- 客户端代码独立于 `server/` 目录放置，并通过 HTTP API 与后端交互，尽量减少实现耦合。
- 新增请求录制回放 MVP：记录关键请求/响应并支持在客户端内执行一次回放。
- 同步产出 UI 设计参考文档，作为页面布局与交互规范依据。
- 补齐与示例客户端相关的文档与集成测试入口，确保该客户端可用于 E2E 场景。

## Capabilities

### New Capabilities
- `builtin-e2e-example-client`: 提供独立端口运行的内建示例客户端，覆盖技能读取、执行、交互与结果展示全流程。

### Modified Capabilities
- `management-api-surface`: 增加面向客户端动态表单构建所需的 Skill 输入/参数 schema 获取能力。

## Impact

- 新增独立客户端目录（不在 `server/` 下）：
  - `e2e_client/app.py`（独立服务入口）
  - `e2e_client/config.py`（端口与后端地址配置，默认 8011 + 环境变量覆盖）
  - `e2e_client/routes/*.py`
  - `e2e_client/templates/*.html`
  - `e2e_client/recordings/*`（录制回放数据）
- 管理 API 扩展（Skill schema 读取能力）：
  - `server/routers/management.py`
  - `server/models.py`
- 文档：
  - `docs/api_reference.md`
  - `docs/dev_guide.md`
  - `docs/e2e_example_client_ui_reference.md`
- 测试：
  - `tests/integration/test_e2e_example_client.py`
  - `tests/e2e/*`（补充示例客户端路径）
