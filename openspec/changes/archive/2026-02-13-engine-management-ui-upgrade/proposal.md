## Why

当前 UI 仅支持 Skill 管理，不支持 Engine 运行时管理。用户缺少可视化手段来：

1. 查看后端 Agent CLI 的可用性与版本；
2. 在界面中触发 CLI 升级并查看执行结果。
3. 管理与 Engine 版本关联的 Model Manifest（查看当前快照、补录当前版本快照）。

在本地与容器环境中，Engine 可用性和版本状态会直接影响任务执行稳定性，因此需要将其纳入管理界面。

## What Changes

- 新增 Engine 管理能力（API + UI）：
  - 查看 Engine 可用状态与版本号；
  - 支持“单引擎升级”与“全部升级”；
  - 展示升级任务状态与 per-engine stdout/stderr。
- 新增 Model Manifest 管理能力（API + UI）：
  - 按 Engine 查看当前 `manifest.json`、检测到的 CLI 版本、已解析快照与模型列表；
  - 支持为“当前检测到的 Engine 版本”手动新增快照；
  - 仅支持新增（add-only），不支持编辑/删除，不允许覆盖已有 `models_<version>.json`。
- 新增升级任务管理组件：
  - 异步升级任务；
  - 全局互斥（同一时刻只允许一个升级任务）；
  - 结构化保存 per-engine 执行结果。
- 更新文档与测试，覆盖本地/容器常见升级行为与失败路径。

## Impact

- 新增引擎升级任务的数据模型与存储。
- 新增/扩展 `/v1/engines/*` 升级接口。
- 新增/扩展 `/v1/engines/*` 的 Model Manifest 查询与新增接口。
- 新增 `/ui/engines` 页面及状态轮询片段。
- 新增 `/ui/engines/{engine}/models` 管理页面（列表+表单）。
- 扩展 `scripts/agent_manager.sh` 支持单引擎升级入口。
