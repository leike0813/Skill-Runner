# external-runtime-harness-cli Specification

## Purpose
定义 harness CLI 的独立入口、参数透传和与主服务解耦的约束。

## MODIFIED Requirements

### Requirement: Harness CLI MUST 提供独立入口并保持与主服务解耦
系统 MUST 提供独立的 harness CLI 入口，运行于独立代码目录；其执行不依赖启动主服务 UI 或改写主服务路由行为。

#### Scenario: 独立入口可执行
- **WHEN** 用户在项目根目录调用 harness CLI
- **THEN** CLI 可以在不启动主服务开发服务器的前提下执行
- **AND** 主服务对外 API 路径与行为不因 harness 存在而改变
