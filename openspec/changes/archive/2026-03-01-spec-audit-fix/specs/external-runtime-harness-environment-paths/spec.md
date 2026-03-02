# external-runtime-harness-environment-paths Specification

## Purpose
定义 harness 的本地部署同源环境继承和 run root 重定向策略。

## MODIFIED Requirements

### Requirement: Harness MUST 默认继承本地部署同源环境语义
系统 MUST 默认复用与本地部署脚本一致的 managed prefix 相关环境语义，包括数据目录、agent cache、agent home、npm prefix 与 uv 路径。

#### Scenario: 默认环境值与本地部署语义一致
- **WHEN** 用户未显式提供 harness 环境覆盖
- **THEN** harness 读取并使用与本地部署同源的 managed prefix 相关环境变量
- **AND** 执行路径优先使用 managed prefix 下的引擎二进制
