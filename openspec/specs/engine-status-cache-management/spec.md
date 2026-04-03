# engine-status-cache-management Specification

## Purpose
定义 engine 版本缓存的 SQLite SSOT、受控探测触发时机，以及页面和 management API 的只读缓存语义。

## Requirements
### Requirement: Engine 版本状态 MUST 持久化到统一数据库缓存
系统 MUST 将 engine 版本探测结果写入 `runs.db` 的 `engine_status_cache` 表，作为 engine 管理域的版本缓存 SSOT。

#### Scenario: 完成版本探测后写缓存
- **WHEN** 服务完成 engine 版本探测
- **THEN** MUST 将结果写入 `runs.db.engine_status_cache`

### Requirement: Engine 版本探测 MUST 仅在受控时机触发
系统 MUST 将 engine 版本探测限制在 startup、升级成功后和每日后台任务，不允许页面/API 读路径触发探测。

#### Scenario: startup 刷新
- **WHEN** 服务启动
- **THEN** MUST 执行一次全量版本探测并刷新缓存

#### Scenario: 升级成功后局部刷新
- **WHEN** 某个 engine 升级成功
- **THEN** MUST 仅刷新该 engine 的缓存项

#### Scenario: 每日后台刷新
- **WHEN** 到达每日后台调度时机
- **THEN** MUST 执行一次全量版本探测并刷新缓存

#### Scenario: 页面和 management API 读路径
- **WHEN** 用户访问 `/ui/engines` 或客户端调用 `GET /v1/management/engines*`
- **THEN** 系统 MUST NOT 触发版本探测

### Requirement: Engine 版本读取 MUST 对缺失或损坏缓存降级
系统 MUST 在缓存缺失、损坏或部分引擎缺项时返回稳定结果，而不是现场探测。

#### Scenario: 缓存缺失或损坏
- **WHEN** `runs.db.engine_status_cache` 缺失、损坏或缺少部分引擎
- **THEN** 页面/API 仍返回稳定结构
- **AND** 缺失版本以 `null` 或 `-` 表示
- **AND** 不在读路径上临时触发 CLI probe

#### Scenario: subset bootstrap keeps uninstalled engines readable
- **WHEN** bootstrap/install 仅对 engine 子集执行 ensure
- **THEN** 未请求安装的 engine 在缓存/UI/API 中仍以稳定结构呈现
- **AND** 未安装 engine 表现为 `present=false` 与空版本
- **AND** 读路径不会因其缺失而触发临时安装或探测

### Requirement: 旧 auth probe API MUST 下线
系统 MUST 下线 engine 管理域的旧 auth probe API，避免继续暴露误导性摘要能力。

#### Scenario: 调用旧 auth probe API
- **WHEN** 客户端调用 `GET /v1/engines/auth-status`
- **THEN** 该接口不再可用
