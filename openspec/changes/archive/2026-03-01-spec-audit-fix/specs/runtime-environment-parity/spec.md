# runtime-environment-parity Specification

## Purpose
定义运行时配置的统一解析和 Managed Prefix 管理 Engine CLI 的约束。

## MODIFIED Requirements

### Requirement: 系统 MUST 统一解析运行时配置
系统 MUST 通过统一解析逻辑确定运行模式、平台和默认路径，供服务与脚本共同使用。

#### Scenario: 自动识别容器模式
- **WHEN** 服务运行在容器环境
- **THEN** 解析结果为 `runtime_mode=container`
- **AND** 导出容器默认目录集合

#### Scenario: 自动识别本地 Windows 模式
- **WHEN** 服务运行在 Windows 本地环境
- **THEN** 解析结果为 `runtime_mode=local` 且 `platform=windows`
- **AND** 使用 Windows 本地默认路径
