# Run 双链路收敛分叉点清单（installed skill vs temp skill）

## 范围与结论

本清单基于当前代码实现核查（2026-03-05），目标是回答：

- 正式 Skill 与临时 Skill 目前还剩哪些分叉点；
- 每个分叉点的风险与改造成本；
- 推荐的收敛顺序。

结论：**核心 attempt 执行主链路已统一**（均进入 `job_orchestrator.run_job(...)`），但在“持久化与入口编排层”仍有中度分叉。

---

## 一、分叉点清单（含风险与成本）

| ID | 维度 | 当前分叉点 | 主要风险 | 改造成本 | 建议优先级 |
|---|---|---|---|---|---|
| B-P1 | 后端-持久化 | `run_store` 与 `temp_skill_run_store` 并存；temp 仍需同步桥接到 run_store（`temp_skill_runs.py::_ensure_temp_request_synced_in_run_store`） | 双写/同步失败导致状态漂移；排障成本高 | L | P0 |
| B-P2 | 后端-持久化 | cache 命名空间分叉：`cache_entries` vs `temp_cache_entries`（`run_store.py`） | 命中行为与统计口径分裂；回收与审计复杂 | M | P1 |
| B-P3 | 后端-持久化 | temp 生命周期与清理链路仍在（`temp_skill_cleanup_manager.start()`；`temp_skill_run_manager.on_terminal(...)`） | “已统一”的认知与实际不一致；线上行为难预测 | M | P0 |
| B-E1 | 后端-执行 | create-run/materialize 阶段双入口（`/jobs` vs `/temp-skill-runs`）且流程重复度高 | 修复要双改，回归风险翻倍 | M | P0 |
| B-E2 | 后端-执行 | source adapter 语义分叉影响 resume/cancel：installed 返回 `temp_request_id=None`，temp 返回 request_id（`run_source_adapter.py`） | 交互/恢复路径行为不一致；容易出现“某路径漏同步” | M | P0 |
| B-E3 | 后端-执行 | router 内仍保留本地 adapter 实现（`jobs.py` / `temp_skill_runs.py`）与 `run_source_adapter.py` 重复 | 同语义多实现导致漂移 | S | P1 |
| F-O1 | 前端-观测 | e2e 观测依赖 `run_source` 选择 `/v1/jobs/*` 或 `/v1/temp-skill-runs/*`（`e2e_client/backend.py::_run_base_path`） | run_source 缺失/错误时请求打到错误链路 | M | P0 |
| F-O2 | 前端-观测 | `_resolve_run_source` 默认回落 installed（`e2e_client/routes.py`） | temp run 在缺少 source 时被误判为 installed | S | P0 |
| F-R1 | 前端-回放 | 用户端回放入口仍按 source 双分支；管理端回放基本单分支（转发 jobs router） | 不同前端渠道看到不同恢复语义 | M | P1 |

---

## 二、关键证据（代码锚点）

- 双 router 双入口与本地 adapter：
  - `server/routers/jobs.py`
  - `server/routers/temp_skill_runs.py`
- 统一 adapter 模块（但未被 router 完全复用）：
  - `server/runtime/observability/run_source_adapter.py`
- 统一执行主链路：
  - `server/services/orchestration/job_orchestrator.py`
  - `server/services/orchestration/run_job_lifecycle_service.py`
- temp 生命周期与清理仍在：
  - `server/main.py`（`temp_skill_cleanup_manager.start()`）
  - `server/services/skill/temp_skill_run_manager.py`
  - `server/services/skill/temp_skill_cleanup_manager.py`
- e2e 双路径与默认 installed 回落：
  - `e2e_client/backend.py`
  - `e2e_client/routes.py`
  - `e2e_client/templates/run_observe.html`
- 管理端事件/聊天回放单路径转发 jobs router：
  - `server/routers/management.py`

---

## 三、收敛建议（按收益/风险比排序）

### P0（先做，降低线上不一致风险）

1. **统一 source adapter 实现入口**
   - 删除 router 内本地 `_InstalledRouterSourceAdapter` / `_TempRouterSourceAdapter`；
   - 全部改为引用 `run_source_adapter.py` 的 adapter。
   - 价值：同语义单实现，立即降低漂移。

2. **消除前端“silent fallback=installed”**
   - `e2e_client/routes.py::_resolve_run_source` 不再默认 installed；
   - source 缺失时：优先后端查询 request 元数据显式判定，否则报错。
   - 价值：避免 temp run 被打到错误 API 家族。

3. **收敛 temp 生命周期的“残留控制面”**
   - 明确 temp cleanup 是否保留；若已决议废弃，则关闭调度器并移除 terminal callback 分支。
   - 价值：行为与架构认知一致，减少不可见副作用。

### P1（第二阶段，降低维护成本）

4. **统一 create-run 编排骨架**
   - 保留 skill materialization 分叉；
   - 抽取“公共 create-run pipeline（校验、request 建立、manifest/cache 计算、dispatch）”。
   - 价值：后续功能只改一处，回归面明显缩小。

5. **合并 cache namespace 策略**
   - 统一到单 cache table + source 字段，或建立统一访问层避免上层感知双表。
   - 价值：统计、回收、排障一致。

6. **统一前端观测/回放入口协议**
   - 用户端与管理端都通过统一 backend 入口访问，再由服务端内部路由 source；
   - 前端不再持有 source 分叉逻辑。
   - 价值：前端代码收敛，减少“同 run 不同页面表现差异”。

### P2（可选，结构化收尾）

7. **评估移除 temp 独立 store 的可行性**
   - 若 temp 与 installed 已统一到同生命周期，可考虑归并为同一 request/run 数据模型，仅保留“skill_source 类型差异”。
   - 价值：从根上消除双写与同步桥接。
   - 成本：高，需要一次完整迁移与回归。

---

## 四、建议的落地节奏（最小风险）

### 阶段 A（1~2 个小 change）
- 先做 P0-1、P0-2（低侵入高收益）；
- 同时补回归：
  - temp run 交互/回放路径正确性；
  - source 缺失时不再误路由。

### 阶段 B（1 个中等 change）
- 做 P0-3 + P1-4（生命周期残留清理 + create-run 公共骨架）。

### 阶段 C（1~2 个中等 change）
- 做 P1-5 + P1-6（缓存与前端入口收敛）。

### 阶段 D（可选大改）
- 评估 P2-7（存储模型归并）。

---

## 五、建议你立即决策的两件事

1. temp cleanup/scheduler 是否**正式退役**（是/否）；
2. 前端 source 判定策略是否改为“**缺失即报错，不默认 installed**”。

这两个决策会直接决定 P0 能否一次性收口。
