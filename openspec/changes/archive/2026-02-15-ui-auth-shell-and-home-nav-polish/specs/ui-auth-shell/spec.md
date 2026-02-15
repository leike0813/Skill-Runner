## ADDED Requirements

### Requirement: 系统 MUST 提供受控的 UI 鉴权终端会话
系统 MUST 在 `/ui` 下提供用于 Engine 鉴权的网页终端能力，并在 managed 环境中执行预置命令。

#### Scenario: 使用预置命令启动会话
- **WHEN** 用户在 UI 中选择一个预置鉴权命令并启动会话
- **THEN** 系统在 managed 环境中启动对应 Engine CLI
- **AND** 页面可实时看到 stdout/stderr 输出

#### Scenario: 拒绝任意命令输入
- **WHEN** 请求携带非白名单命令或原始 shell 字符串
- **THEN** 系统拒绝执行
- **AND** 返回可识别错误信息

### Requirement: 系统 MUST 全局限制为单个活跃会话
系统 MUST 在同一时刻最多只允许一个 UI shell 会话，避免并发争用与安全面扩大。

#### Scenario: 并发创建会话
- **WHEN** 已有活跃会话且再次发起新会话
- **THEN** 系统返回 busy 错误
- **AND** 不启动第二个进程

### Requirement: 系统 MUST 对会话执行超时与清理
系统 MUST 在会话空闲超时或硬超时后结束会话并清理相关进程。

#### Scenario: 触发 idle timeout
- **WHEN** 会话在配置时间内无有效交互
- **THEN** 系统终止会话进程
- **AND** 会话状态标记为 timeout/closed

#### Scenario: 触发 hard TTL
- **WHEN** 会话达到最大生命周期
- **THEN** 系统强制终止进程
- **AND** 记录终止原因用于排障

### Requirement: 系统 MUST 保持 UI 基础鉴权保护
UI 鉴权终端相关页面与接口 MUST 继续受 UI Basic Auth 保护。

#### Scenario: 未鉴权访问终端页面/接口
- **WHEN** 请求未提供或提供错误的 Basic Auth 凭证
- **THEN** 系统返回 401
- **AND** 不暴露终端会话状态或输出内容

### Requirement: 系统 MUST 支持 Windows 本地完整终端能力
系统 MUST 在 Windows 本地部署时提供可交互终端能力；若运行依赖缺失，需返回明确可操作错误。

#### Scenario: Windows 依赖存在
- **WHEN** 在 Windows 本地环境启动 UI 鉴权终端
- **THEN** 会话可正常运行并交互显示输出

#### Scenario: Windows 依赖缺失
- **WHEN** 在 Windows 本地环境缺少终端运行依赖
- **THEN** 系统返回明确错误，指出缺失依赖及安装建议
