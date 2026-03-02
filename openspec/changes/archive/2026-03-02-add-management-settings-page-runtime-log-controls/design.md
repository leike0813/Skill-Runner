## Overview

本 change 同时处理三个紧密相关的问题：

1. 管理首页不再承载高危 data reset 区。
2. reset UI 必须与 `engine auth session` 日志能力状态保持一致。
3. 日志最小可写设置需要一个运行时持久化与热重载机制。

实现上采用“页面迁移 + 最小设置服务 + logging 重载”的组合，而不引入通用动态配置框架。

## Settings Persistence Model

### Persisted file

- 运行时 settings 文件：`data/system_settings.json`
- bootstrap 文件：`server/assets/configs/system_settings.bootstrap.json`

### Scope

`data/system_settings.json` 只包含 UI 可写日志项：

- `logging.level`
- `logging.format`
- `logging.retention_days`
- `logging.dir_max_bytes`

以下日志项不进入 settings 文件，继续走原有配置入口并允许环境变量覆盖：

- `logging.dir`
- `logging.file_basename`
- `logging.rotation_when`
- `logging.rotation_interval`

### Service

新增 `SystemSettingsService`：

- 首次读取时若 settings 文件不存在，则由 bootstrap 文件复制生成
- 负责校验、原子写入、读取有效 settings
- 对外返回“可写配置 + 只读运行时输入”的统一视图

## Logging Reload Model

`server/logging_config.py` 新增重载能力：

- 通过 `SystemSettingsService` 读取可写项
- 与 `core_config/env` 中的只读日志项合并成最终 `LoggingSettings`
- 原子移除旧 handlers 后重建 stream/file handlers
- 重设 `apscheduler` logger 级别
- 保持重复调用幂等

失败时：

- file handler 初始化失败则退回 stream-only
- settings 写入失败时 API 返回错误，不做部分提交

## Management API

新增：

- `GET /v1/management/system/settings`
- `PUT /v1/management/system/settings`

请求/响应模型放入 `server/models/management.py`。

`PUT` 仅接受日志最小可写集；若传入只读字段则返回 `400`。

现有：

- `POST /v1/management/system/reset-data`

保持兼容，但在 feature off 时会把 `include_engine_auth_sessions` 归一化为 `False`。

## UI Structure

### Home

`/ui` 首页：

- 保留 skills/install/navigation
- 移除 danger zone
- 新增 Settings 导航卡片

### Settings

`/ui/settings` 新页面：

- `Logging Settings`
  - 编辑区：`level / format / retention_days / dir_max_bytes`
  - 只读区：`dir / file_basename / rotation_when / rotation_interval`
- `Danger Zone / Data Reset`
  - 迁移现有确认弹窗与确认文本输入机制
  - 当 `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=False` 时，完全不渲染 engine auth session 清理选项

## Data Reset Integration

`data_reset_service` 调整：

- 把 `data/system_settings.json` 纳入可选清理目标
- 仅当 `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=True` 时，允许把 `data/engine_auth_sessions` 纳入目标集

## Testing Strategy

- 新增 `test_system_settings_service.py`
- 更新 `test_logging_config.py`：验证 settings 文件驱动与热重载
- 更新 `test_management_routes.py`：覆盖 settings GET/PUT 与 reset capability 归一化
- 更新 `test_ui_routes.py`：覆盖 `/ui/settings` 和首页去除 danger zone
- 更新 `test_data_reset_service.py`：覆盖 `system_settings.json` 和 engine auth session 目标规则
