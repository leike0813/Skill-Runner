## Purpose
定义 Engine 升级任务与 Model Manifest 管理的服务端接口与约束，确保升级流程可追踪、可观测，并确保模型快照以 add-only 方式安全维护。
## Requirements
### Requirement: 系统 MUST 提供引擎升级任务创建接口
系统 MUST 在创建升级任务前基于 managed prefix 判定引擎安装状态，不得被全局 PATH 可执行项误判短路。

#### Scenario: global 可执行但 managed 缺失
- **WHEN** 某 engine 在全局 PATH 可执行但 managed prefix 下缺失
- **THEN** `ensure/upgrade` 逻辑仍按 managed 缺失处理
- **AND** 安装目标为 managed prefix

### Requirement: 系统 MUST 提供升级任务状态查询接口
系统 MUST 提供按 `request_id` 查询升级任务状态的接口。

#### Scenario: 查询运行中任务
- **WHEN** 客户端查询运行中任务
- **THEN** 返回 `status=running`
- **AND** 返回当前可用的 per-engine 执行结果片段

### Requirement: 升级结果 MUST 包含 per-engine stdout/stderr
系统 MUST 在路径跑偏或安装失败时输出可诊断信息，帮助定位 managed/global 冲突。

#### Scenario: managed 安装失败
- **WHEN** 某 engine 安装到 managed prefix 失败
- **THEN** 返回该 engine 的 `status=failed`
- **AND** `stderr` 中包含安装失败上下文

### Requirement: 系统 MUST 限制同一时刻仅一个升级任务
系统 MUST 保证同一时刻只有一个升级任务处于 running 状态。

#### Scenario: 并发创建任务
- **WHEN** 已有升级任务处于 `running`
- **THEN** 新建升级请求被拒绝（冲突状态码）

### Requirement: 系统 MUST 提供 Engine Model Manifest 查询接口
系统 MUST 在容器模式与本地模式下使用同一运行时环境解析策略完成版本检测与 manifest 查询。

#### Scenario: 本地模式查询 manifest
- **WHEN** 客户端请求 `GET /v1/engines/{engine}/models/manifest`
- **THEN** 返回 `cli_version_detected` 与 manifest 视图
- **AND** 检测路径来自受管运行时配置（非硬编码容器路径）

### Requirement: 系统 MUST 仅允许为当前检测版本新增快照
系统 MUST 将新增快照版本绑定到当前 `cli_version_detected`，且不允许请求方覆盖版本来源。

#### Scenario: 检测到版本并新增成功
- **WHEN** 请求 `POST /v1/engines/{engine}/models/snapshots` 且提供合法 `models`
- **THEN** 系统以当前 `cli_version_detected` 创建 `models_<version>.json`
- **AND** 更新该 Engine 的 `manifest.json`

#### Scenario: 无法检测版本时拒绝
- **WHEN** 当前 Engine 无法检测 CLI 版本
- **THEN** 新增快照请求被拒绝（冲突类错误）

### Requirement: Model 快照写入 MUST 遵循 add-only/no-overwrite
系统 MUST 不覆盖已有 `models_<version>.json`，目标文件存在时必须拒绝。

#### Scenario: 目标版本快照已存在
- **WHEN** `models_<detected_version>.json` 已存在
- **THEN** 新增请求被拒绝
- **AND** 现有 manifest 与快照文件保持不变

### Requirement: 新增快照后 MUST 立即刷新 Model Registry
系统 MUST 在新增快照成功后立即刷新内存模型注册表。

#### Scenario: 新增后立即可见
- **WHEN** 新增快照请求成功
- **THEN** 后续 `GET /v1/engines` 能读取到更新后的模型列表

