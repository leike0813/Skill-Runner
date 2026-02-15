# ui-engine-inline-terminal Specification

## Purpose
TBD - created by archiving change engine-ui-inline-tui-terminal. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供受控的 UI 鉴权终端会话
系统 MUST 在 `/ui/engines` 页面内提供终端会话能力，并在 managed 环境中执行预置引擎命令。

#### Scenario: 启动后即时可观测
- **WHEN** 用户成功启动任一引擎 TUI
- **THEN** WebSocket 建连后立即收到 state 帧
- **AND** 终端显示至少一条握手输出（非空白）

### Requirement: 系统 MUST 采用每引擎单命令模型
系统 MUST 仅允许每个引擎一个 TUI 命令入口，不暴露 login/auth/version/interactive 多模式。

#### Scenario: 命令入口约束
- **WHEN** 用户从 UI 启动会话
- **THEN** 可选项仅为 `codex`、`gemini`、`iflow` 对应 TUI 命令
- **AND** 系统拒绝任何非白名单命令 ID

### Requirement: 系统 MUST 对内嵌终端启用 fail-closed 沙箱策略
系统 MUST 在启动引擎 TUI 前完成 sandbox 可用性探测并暴露结果；探测结果默认用于可观测，不作为阻断启动的硬门槛。

#### Scenario: sandbox 探测为 supported
- **WHEN** 用户点击某引擎“在内嵌终端中启动 TUI”
- **AND** sandbox 探测结果为 `supported`
- **THEN** 系统启动会话并附加终端
- **AND** 会话状态中记录 `sandbox_status=supported`

#### Scenario: sandbox 探测为 unsupported/unknown
- **WHEN** 用户点击某引擎“在内嵌终端中启动 TUI”
- **AND** sandbox 探测结果为 `unsupported` 或 `unknown`
- **THEN** 系统仍尝试启动会话
- **AND** UI 显示非阻断 warning
- **AND** 会话状态中记录对应 `sandbox_status`

### Requirement: 系统 MUST 将会话写入范围限制在隔离目录与 agent_home
系统 MUST 为每个内嵌终端会话创建独立工作目录，并将写入范围限制在该会话目录与 `agent_home`。

#### Scenario: 启动会话时创建隔离目录
- **WHEN** 用户成功启动任一引擎 TUI
- **THEN** 系统创建 `data/ui_shell_sessions/<session_id>` 作为会话工作目录
- **AND** CLI 进程在该目录运行

#### Scenario: 写入边界约束
- **WHEN** 会话执行中发生文件写入
- **THEN** 仅允许写入 `session_dir` 与 `agent_home`
- **AND** 不应获得项目其它目录写入权限

### Requirement: 系统 MUST 提供可渲染复杂 TUI 的终端仿真
系统 MUST 使用支持 ANSI/VT 控制序列的终端仿真渲染方案，以保证 Agent CLI 的复杂 TUI 正常显示。

#### Scenario: 控制序列渲染
- **WHEN** CLI 输出包含颜色、光标移动、清屏或重绘控制序列
- **THEN** 前端终端按终端语义渲染
- **AND** 不应以原始乱码文本形式展示控制序列

### Requirement: 系统 MUST 以内置静态资源提供终端前端依赖
系统 MUST 将终端渲染依赖作为服务静态资源提供，不依赖外部 CDN 可达性。

#### Scenario: 离线/内网访问 UI
- **WHEN** 浏览器无法访问公网 CDN
- **THEN** UI 仍可从服务静态路径加载终端脚本和样式
- **AND** 内嵌终端功能可正常启动

### Requirement: 系统 MUST 保持单会话并提供显式停止能力
系统 MUST 在任意时刻仅允许一个活跃引擎终端会话，并提供可操作的停止入口。

#### Scenario: 并发启动
- **WHEN** 已有活跃会话时再次启动其他引擎 TUI
- **THEN** 系统返回 busy 错误
- **AND** 不创建第二个会话

#### Scenario: 用户主动停止
- **WHEN** 用户点击停止终端
- **THEN** 系统终止当前会话进程（含子进程）
- **AND** 页面状态更新为已结束

### Requirement: 系统 MUST 采用“可点击后即时反馈”的按钮交互
系统 MUST 保持启动按钮可点击，并在点击后即时给出 sandbox 校验结果，而非预先禁用按钮。

#### Scenario: 点击后失败反馈
- **WHEN** 用户点击启动按钮但当前引擎 sandbox 不可用
- **THEN** 页面立即展示错误反馈
- **AND** 启动按钮保持可见以便用户重试

