## ADDED Requirements

### Requirement: 旧 UI 数据接口 MUST 进入弃用生命周期
系统 MUST 为历史 UI 专用数据接口提供可执行的弃用路径，并给出替代 management API。

#### Scenario: Deprecation 标记
- **WHEN** 客户端调用旧 UI 数据接口
- **THEN** 响应包含弃用提示（文档与/或响应元信息）
- **AND** 明确替代 management API 路径

#### Scenario: 内建 UI 脱离旧接口
- **WHEN** 弃用阶段完成
- **THEN** 内建 Web 客户端不再调用旧 UI 数据接口
- **AND** 核心管理页面功能保持可用
