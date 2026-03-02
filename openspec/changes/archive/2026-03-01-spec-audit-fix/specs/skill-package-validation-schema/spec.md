# skill-package-validation-schema Specification

## Purpose
定义 skill 包校验合同的独立 schema 文件声明和安装/临时上传共用同一 manifest 合同的约束。

## MODIFIED Requirements

### Requirement: Skill package 校验合同 MUST 以独立 schema 文件声明
系统 MUST 提供独立的 schema 文件来声明 skill package 与 `assets/runner.json` 的校验合同，而非仅依赖服务内硬编码规则。

#### Scenario: 校验入口加载独立 schema
- **WHEN** 系统启动安装或临时上传校验流程
- **THEN** 系统从独立 schema 文件加载并执行结构化校验
- **AND** 校验失败信息可映射为稳定的字段级错误
