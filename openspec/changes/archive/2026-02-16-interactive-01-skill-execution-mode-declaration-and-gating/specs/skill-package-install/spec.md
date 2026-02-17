## ADDED Requirements

### Requirement: 安装校验 MUST 包含 execution_modes 声明
系统 MUST 在 skill 包安装/更新校验中要求 `runner.json.execution_modes` 为合法声明。

#### Scenario: 安装包声明 execution_modes
- **WHEN** 上传 skill 包用于安装或更新
- **THEN** 系统校验 `execution_modes` 为非空且值在 `auto|interactive` 枚举内

#### Scenario: 安装包缺失 execution_modes
- **WHEN** 上传包缺失 `execution_modes` 或声明非法值
- **THEN** 系统拒绝安装并返回校验错误
