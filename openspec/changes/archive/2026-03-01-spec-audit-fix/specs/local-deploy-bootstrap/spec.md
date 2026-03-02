# local-deploy-bootstrap Specification

## Purpose
定义本地一键部署脚本的依赖检查、路径初始化和运行时解析统一规则。

## MODIFIED Requirements

### Requirement: 系统 MUST 提供本地一键部署脚本
系统 MUST 提供 Linux/macOS 与 Windows 两套本地一键部署脚本，完成基础目录初始化与服务启动准备。

#### Scenario: Linux/macOS 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.sh`
- **THEN** 脚本完成必要路径初始化与前置检查
- **AND** 输出明确的后续启动信息

#### Scenario: Windows 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.ps1`
- **THEN** 脚本完成 Windows 本地路径初始化与前置检查
- **AND** 输出明确的后续启动信息
