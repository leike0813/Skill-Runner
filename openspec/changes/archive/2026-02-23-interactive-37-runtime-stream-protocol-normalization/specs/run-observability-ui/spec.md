## MODIFIED Requirements

### Requirement: Run 页面 MUST 支持对话窗口式管理体验
系统 MUST 让内建 Run 页面以统一对话协议（FCMP）驱动会话展示与交互控制：对话区消费 `assistant.message.*`，输入区消费/提交 `user.input.*`，stderr 与诊断信息独立可读。

#### Scenario: waiting_user 交互
- **WHEN** Run 状态进入 `waiting_user`
- **THEN** 页面展示 `user.input.required` 对应的交互提示
- **AND** 激活底部输入框用于提交 reply

#### Scenario: 实时对话更新
- **WHEN** 页面收到 FCMP 对话事件
- **THEN** 页面按 `seq` 顺序渲染对话消息
- **AND** 断线重连后可基于 cursor 续传恢复

#### Scenario: stderr 与诊断独立展示
- **WHEN** 页面收到 raw/stderr 或 diagnostic 事件
- **THEN** 页面在独立错误与诊断窗口中展示
- **AND** 不干扰主对话阅读与输入操作

## ADDED Requirements

### Requirement: Run 页面 MUST 支持原始流与结构化流联动排障
系统 MUST 提供从结构化消息回跳到原始日志区间的能力，以支撑运行时解析问题排查。

#### Scenario: 从对话事件定位原始日志
- **WHEN** 用户在页面中查看某条结构化消息
- **THEN** 页面可使用 `raw_ref` 跳转到对应 stdout/stderr 区间
- **AND** 用户可对照查看结构化事件与原始输出

### Requirement: Run 页面 MUST 规范展示诊断与低置信度信息
系统 MUST 以可读且不干扰主对话的方式展示诊断事件与低置信度解析结果。

#### Scenario: 低置信度消息标注
- **WHEN** 对话消息对应的解析置信度低于阈值
- **THEN** 页面在该消息处展示低置信度标识
- **AND** 用户可展开查看对应诊断码与解释

#### Scenario: 诊断事件分区展示
- **WHEN** 页面接收到 `diagnostic.warning` 或 `diagnostic.error`
- **THEN** 诊断信息在独立区域展示
- **AND** 默认折叠原始噪声片段，避免淹没主对话内容

#### Scenario: raw 事件不进入主对话时间线
- **WHEN** 页面接收到 `raw.stdout` 或 `raw.stderr`
- **THEN** 默认仅在“原始日志/诊断”分区展示
- **AND** 主对话时间线只展示 `assistant.message.*`、`user.input.*` 与会话终态事件

### Requirement: Run 页面 MUST 提供事件关联可视化
系统 MUST 在 Run 观测页面提供基于关联字段的事件关系视图，帮助用户理解请求、回复、工具调用与产物事件之间的因果链路。

#### Scenario: 展示关联关系
- **WHEN** 页面收到包含 `correlation` 信息的事件
- **THEN** 页面可按 `session_id`、`parent_seq` 或等价关联键聚合事件
- **AND** 用户可在关系视图中查看关键链路节点

#### Scenario: 从关联视图回跳详情
- **WHEN** 用户在关系视图中选择某个节点
- **THEN** 页面跳转到对应对话/诊断事件详情
- **AND** 支持继续使用 `raw_ref` 查看原始日志区间
