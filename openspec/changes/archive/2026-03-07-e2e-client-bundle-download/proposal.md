## Why

E2E 客户端当前可浏览 bundle 文件树与文件预览，但缺少“一键下载完整 bundle”能力。  
这会让调试与问题复现过程需要额外进入管理端或手工调用 API，效率低且链路不完整。

## What Changes

- 为 E2E Run Observation 增加“下载 bundle”入口（按钮）。  
- 在 E2E 代理层增加 bundle 下载转发接口，直接透传后端 `/v1/jobs/{request_id}/bundle` 二进制内容。  
- 下载行为与现有 run source 路径保持一致（使用当前 run scope，不新增执行语义）。  
- 补充失败处理：后端不可达、run 不存在、bundle 构建失败时给出稳定错误反馈。  
- 同步 UI 文案与测试，保证下载功能不影响现有文件树/预览链路。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `builtin-e2e-example-client`: 新增 E2E Run Observation 的 bundle 下载交互能力。  
- `interactive-job-api`: 明确 E2E 客户端可通过代理稳定消费 run bundle 下载能力。

## Impact

- Affected code:
  - `e2e_client/routes.py`
  - `e2e_client/backend.py`
  - `e2e_client/templates/run_observe.html`
  - `server/locales/*.json`（下载按钮与错误文案）
- API impact:
  - E2E 本地代理新增下载端点（仅客户端内部使用）。
  - 后端公开 API 不新增路径。
- Protocol impact: None.
