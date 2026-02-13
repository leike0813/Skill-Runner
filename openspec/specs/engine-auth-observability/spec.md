# engine-auth-observability Specification

## Purpose
TBD - created by archiving change engine-auth-observability-and-failfast. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供统一 Engine 鉴权状态接口
系统 MUST 提供统一接口返回各 Engine 的鉴权可观测状态，且输出结构可被 UI 与脚本复用。

#### Scenario: 查询鉴权状态成功
- **WHEN** 客户端请求 `GET /v1/engines/auth-status`
- **THEN** 返回每个 engine 的 `managed_present`、`effective_cli_path`、`effective_path_source`
- **AND** 返回白名单凭证文件存在性明细

### Requirement: 系统 MUST 区分 managed 与 global CLI 路径来源
系统 MUST 明确标识当前实际可执行路径来源，避免用户误把全局 CLI 当作 managed CLI。

#### Scenario: managed 缺失但 global 可用
- **WHEN** managed prefix 下不存在某 engine 可执行文件，但 PATH 中存在全局可执行
- **THEN** 状态中 `effective_path_source` 标记为 `global`
- **AND** 提供诊断提示建议安装到 managed prefix

### Requirement: 系统 MUST 提供本地与容器一致的鉴权诊断脚本
系统 MUST 提供脚本化方式输出当前运行时真实鉴权状态。

#### Scenario: 本地运行诊断脚本
- **WHEN** 用户执行鉴权诊断脚本
- **THEN** 脚本输出服务当前 runtime 下各 engine 的路径来源与凭证状态

### Requirement: 系统 MUST 保证 iFlow 在 managed 环境具备最小可用配置基线
系统 MUST 在 managed Agent Home 中确保 iFlow settings 包含可用认证类型与 API 端点，避免因配置缺失导致鉴权状态误判。

#### Scenario: iFlow settings 缺失时初始化基线
- **WHEN** managed `~/.iflow/settings.json` 不存在
- **THEN** 系统写入默认基线配置
- **AND** 至少包含 `selectedAuthType=oauth-iflow` 与 `baseUrl=https://apis.iflow.cn/v1`

#### Scenario: iFlow legacy settings 自动迁移
- **WHEN** managed `~/.iflow/settings.json` 存在但 `selectedAuthType=iflow` 或 `baseUrl` 缺失/非法
- **THEN** 系统自动迁移到默认基线值
- **AND** 不影响白名单凭证文件导入策略（仅导入鉴权文件，不导入外部 settings）

