## Context

当前项目的引擎鉴权路径主要有三类：内嵌 TUI 登录、手动复制凭据文件、Harness 路径下启动 TUI。它们可用但操作门槛较高，且难以在统一 Web 入口中提供稳定体验。  
团队目标是评估“前端暴露 OAuth 鉴权”是否可行，并在不破坏现有运行稳定性的前提下给出后续实现边界。

约束条件：
- 当前 OpenSpec 工作流要求四大工件（proposal/specs/design/tasks）齐备后进入实施阶段。
- 四个引擎的上游 CLI 能力差异明显，不能先验假设都支持同一种 OAuth 代理方式。
- 本 change 定位为预研，不在本阶段提交运行时代码。

## Goals / Non-Goals

**Goals:**
- 给出可复核的 OAuth 代理可行性结论，而非仅给出方向性意见。
- 定义后续实现 change 可直接使用的实施蓝图（接口、分期、风险、验收口径）。
- 在不影响现有引擎执行链路的前提下，建立最小影响的规范化研究输出。

**Non-Goals:**
- 不在本 change 中新增任何 `/ui` 或 `/v1` 鉴权 API。
- 不在本 change 中改动 engine adapter、router、manager 或 UI 模板代码。
- 不承诺四引擎一次性交付统一 OAuth 代理实现。

## Decisions

### 1) 采用“研究先行、实现后置”的两阶段策略

**Decision**  
先完成可行性研究与实施蓝图，再基于结论拆分实现型 change。

**Rationale**  
多引擎上游能力异构，直接编码实现的返工风险高；先收敛证据可避免错误路线。

**Alternatives considered**
- 直接实现统一 OAuth 代理：风险高，且容易被单个引擎能力短板拖累。
- 仅保留现有 TUI/导入方式：无法改善前端易用性目标。

### 2) 使用“分层能力模型”而非“全引擎一刀切”

**Decision**  
后续实现按引擎能力分层：  
- Tier A（可原生代理）：优先走 authorize/callback/token 明确可编排路径。  
- Tier B（可委托编排）：走 CLI 非交互/半交互登录编排，前端仅展示 challenge。  
- Tier C（仅回退）：保留 TUI 一键引导与凭据导入。

**Rationale**  
该模型可最小化阻塞，支持先落地可行引擎，再扩展其余引擎。

**Alternatives considered**
- 统一要求全引擎 Tier A：会导致交付时间不可控。
- 仅做 Tier C：提升有限，不符合“前端 OAuth 能力提升”目标。

### 3) 统一实施蓝图（供后续实现 change 直接复用）

**Decision**  
输出统一实现蓝图，后续实现型 change 按以下模块落地：
- `EngineAuthDriver` 抽象层（每引擎一个 driver）
- `EngineAuthFlowManager`（鉴权会话生命周期）
- UI 路由（start/status/cancel/callback）
- 鉴权会话存储（首期内存+TTL，后续可落盘）
- 观测与审计（事件、错误分类、时延指标）

**Rationale**  
先约束架构边界，避免后续实现中路由、状态、日志语义分裂。

**Alternatives considered**
- 直接在 router 中按引擎硬编码：短期快，长期维护成本高。

### 4) 后续实现建议的最小 API 草案（仅设计，不在本 change 实施）

**Decision**  
建议后续实现型 change 采用以下最小接口集合：
- `POST /ui/engines/auth/sessions`（start）
- `GET /ui/engines/auth/sessions/{id}`（status）
- `POST /ui/engines/auth/sessions/{id}/cancel`（cancel）
- `GET /ui/engines/auth/callback/{engine}`（callback）

并保持与现有 `/v1/engines/auth-status` 兼容联动。

**Rationale**  
最小接口集可覆盖 start→authorize→callback→finalize 全流程，且不破坏既有管理 API。

**Alternatives considered**
- 首期直接开放公共 `/v1`：安全与兼容压力更高，建议后置。

### 5) 安全基线（后续实现必须满足）

**Decision**  
后续实现必须包含：
- state/nonce 防重放
- callback allowlist 与 URI 校验
- 会话 TTL 与单会话互斥策略
- 敏感字段脱敏日志（code/token）
- 基于现有 UI Basic Auth 的访问保护

**Rationale**  
OAuth 流程天然涉及短期敏感凭据，必须先定义安全底线。

## Risks / Trade-offs

- [Risk] 上游 CLI 行为变更导致代理流程失效  
  → Mitigation：driver 版本门控 + 能力探测 + 失败自动回退至现有路径。

- [Risk] 部分引擎无法提供稳定非交互登录入口  
  → Mitigation：采用分层模型，不强求一次性统一。

- [Risk] 前端 OAuth 流程引入额外安全面（callback 劫持、state 重放）  
  → Mitigation：state/nonce、短 TTL、严格回调校验、审计日志。

- [Risk] 研究结论与实现落地脱节  
  → Mitigation：研究报告中强制输出“实现边界 + 验收场景 + 失败退出条件”。

## Migration Plan

本 change 自身无运行时迁移，仅定义后续实施步骤：

1. 新建实现型 change（基于本研究结论，明确首期引擎范围）。
2. 先落地 `EngineAuthDriver` 与 `EngineAuthFlowManager` 骨架。
3. 接入 `/ui` 路由与管理页最小交互，不破坏现有 TUI/导入流程。
4. 灰度启用单引擎试点，验证鉴权成功率与失败回退。
5. 按分层模型逐步扩展到其余引擎。

回滚策略（后续实现阶段适用）：
- 通过 feature flag 一键关闭 OAuth 入口，保留既有鉴权方式。
- 会话管理器失效时回退到 `/ui/engines` 的现有 TUI 启动路径。

## Open Questions

- 各引擎在无头环境下的 OAuth 可编排能力是否可稳定长期维护（需持续版本验证）。
- 是否需要在首期就提供 `/v1` 公共 OAuth API，还是先限定在 `/ui`。
- 会话状态是否需要跨重启恢复（内存 TTL 与落盘恢复的取舍）。
