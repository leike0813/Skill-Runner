## ADDED Requirements

### Requirement: 运行时观测协议层 MUST 通过 Adapter 提供引擎解析结果
系统 MUST 在构建 RASP/FCMP 事件时通过对应引擎 Adapter 获取 runtime 解析结果，而不是在通用协议层维护引擎分支解析逻辑。

#### Scenario: 观测服务构建事件时委托 Adapter 解析
- **WHEN** 观测服务为某 run attempt 构建 RASP 事件
- **THEN** 系统调用对应引擎 Adapter 的 runtime 解析接口获取标准解析结构

### Requirement: 通用协议层 MUST 保持引擎无关
系统 MUST 使通用协议层仅负责事件组装、通用去重和度量计算，不包含 codex/gemini/iflow/opencode 的专用解析分支。

#### Scenario: 协议层无引擎解析分支
- **WHEN** 审查通用协议层实现
- **THEN** 不存在按引擎名称分支的专用解析函数实现
