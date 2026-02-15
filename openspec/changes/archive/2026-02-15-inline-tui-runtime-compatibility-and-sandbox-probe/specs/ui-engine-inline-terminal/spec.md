## MODIFIED Requirements

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

### Requirement: 系统 MUST 提供受控的 UI 鉴权终端会话
系统 MUST 在 `/ui/engines` 页面内提供终端会话能力，并在 managed 环境中执行预置引擎命令。

#### Scenario: 启动后即时可观测
- **WHEN** 用户成功启动任一引擎 TUI
- **THEN** WebSocket 建连后立即收到 state 帧
- **AND** 终端显示至少一条握手输出（非空白）

