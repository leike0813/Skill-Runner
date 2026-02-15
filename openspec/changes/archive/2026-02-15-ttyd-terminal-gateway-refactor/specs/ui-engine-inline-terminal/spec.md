## MODIFIED Requirements

### Requirement: 系统 MUST 提供受控的 UI 鉴权终端会话
系统 MUST 在 `/ui/engines` 页面内提供终端会话能力，并在 managed 环境中执行预置引擎命令。

#### Scenario: 在引擎页面启动 TUI
- **WHEN** 用户在 `/ui/engines` 点击某引擎的“在内嵌终端中启动 TUI”
- **THEN** 系统以 ttyd 网关方式启动该引擎 CLI 的默认 TUI
- **AND** 页面内嵌终端显示该会话输出

### Requirement: 系统 MUST 提供可渲染复杂 TUI 的终端仿真
系统 MUST 采用 ttyd 作为终端网关，以保证 ANSI/VT 控制序列、滚动与交互行为的一致性。

#### Scenario: 复杂控制序列渲染
- **WHEN** CLI 输出包含颜色、光标移动、清屏或重绘控制序列
- **THEN** 内嵌终端按终端语义渲染
- **AND** 不应以原始乱码文本形式展示控制序列

#### Scenario: 选择与复制可用
- **WHEN** 用户在内嵌终端中选择文本并复制
- **THEN** 选择区域应保持可见直至用户完成复制动作
- **AND** 复制内容与终端可见文本一致

### Requirement: 系统 MUST 保持单会话并提供显式停止能力
系统 MUST 在任意时刻仅允许一个活跃引擎终端会话，并提供可操作的停止入口。

#### Scenario: 并发启动
- **WHEN** 已有活跃会话时再次启动其他引擎 TUI
- **THEN** 系统返回 busy 错误
- **AND** 不创建第二个会话

#### Scenario: 用户主动停止
- **WHEN** 用户点击停止终端
- **THEN** 系统终止当前 ttyd 会话及其子进程
- **AND** 页面状态更新为已结束
- **AND** 后续可再次启动新会话

### Requirement: 系统 MUST 将会话写入范围限制在隔离目录与 agent_home
系统 MUST 为每个内嵌终端会话创建独立工作目录，并将写入范围限制在该会话目录与 `agent_home`。

#### Scenario: 启动会话时创建隔离目录
- **WHEN** 用户成功启动任一引擎 TUI
- **THEN** 系统创建 `data/ui_shell_sessions/<session_id>` 作为会话工作目录
- **AND** ttyd 驱动的 CLI 进程在该目录运行

### Requirement: 系统 MUST 以内置或受控依赖方式提供终端能力
系统 MUST 在部署文档中声明 ttyd 依赖，并确保本地部署与容器部署均可用。

#### Scenario: 本地部署缺失 ttyd
- **WHEN** 服务启动后用户尝试启动内嵌终端
- **AND** 系统未发现 ttyd 可执行文件
- **THEN** 系统返回明确可诊断错误（缺失 ttyd）
- **AND** 文档提供安装指引

