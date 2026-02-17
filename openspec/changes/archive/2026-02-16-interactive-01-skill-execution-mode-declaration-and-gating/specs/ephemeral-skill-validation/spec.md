## ADDED Requirements

### Requirement: 临时 Skill 校验 MUST 包含 execution_modes 声明
系统 MUST 在临时 skill 上传校验中要求 `runner.json.execution_modes` 为合法声明。

#### Scenario: 临时包声明 execution_modes
- **WHEN** 客户端上传临时 skill 包
- **THEN** 系统校验 `execution_modes` 为非空且仅包含 `auto|interactive`

#### Scenario: 临时包缺失 execution_modes
- **WHEN** 临时 skill 包缺失 `execution_modes` 或声明非法值
- **THEN** 系统拒绝该上传请求并返回校验错误
