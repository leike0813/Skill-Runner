# Skill Runner v0.5.0

发布日期：2026-04-05

版本类型：重大版本更新

## 发布摘要

v0.5.0 是继 v0.4.0 之后的又一次重大跃迁。本次发布核心围绕多引擎支持与前端体验升级两条主线展开，不仅新增了 Qwen 和 Claude Code 两大引擎，还对消息语义、数学公式渲染、认证体系进行了系统性升级。

## 主要更新

1. 新增多引擎支持架构

- New: Qwen Code 引擎 — 支持阿里 OAuth (**每日1000次免费调用 Qwen 3.6 Plus**)、百炼 Coding Plan （更推荐使用 Claude Code 引擎或 OpenCode 引擎）
- Claude Code 引擎 — 支持官方 OAuth 和第三方 provider
- 通用化 Provider 认证 — 统一的引擎认证策略管理，支持按需安装与热插拔

2. 前端体验显著增强

- Markdown 渲染升级 — 支持 KaTeX 数学公式，学术场景表达更友好
- Agent 消息语义重设计 — 优化 Chat Replay 与运行观测 UI
- 内建技能目录分离 — skills_builtin 与用户技能解耦，便于分发维护

3. 架构与稳定性升级
   
- NDJSON 溢出保护 — 修复大消息流处理边界问题
- 性能优化 — 重构核心路径，修复重大性能瓶颈
- 认证导入服务 — 支持从外部导入凭据，降低迁移成本
- literature-digest 技能重构 — 引用分析流水线质量与可读性提升