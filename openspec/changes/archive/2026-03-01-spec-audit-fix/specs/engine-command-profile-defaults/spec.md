# engine-command-profile-defaults Specification

## Purpose
定义引擎命令行参数 profile 的默认值加载策略，区分 API 链路与 Harness 链路的参数注入行为。

## MODIFIED Requirements

### Requirement: API 链路 MUST 从配置文件加载引擎命令默认参数 Profile
系统 MUST 从 `server/assets/configs/engine_command_profiles.json` 读取并应用 API 链路的引擎命令默认参数 Profile。

#### Scenario: Profile 文件存在且引擎已配置
- **WHEN** API 链路为某引擎构建命令且 Profile 文件包含该引擎默认项
- **THEN** 系统按配置文件内容注入默认参数

#### Scenario: Profile 文件缺失或引擎未配置
- **WHEN** API 链路为某引擎构建命令但无可用 Profile 默认项
- **THEN** 系统使用空默认参数继续构建且不报错中断
