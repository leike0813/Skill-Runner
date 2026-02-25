## Context

Harness 当前 CLI 仅有 `start <engine> ...` / `<engine> ...` 两种启动语法，未提供 execution mode 开关。  
同时 skill 注入路径在 `agent_harness/skill_injection.py` 中硬编码 `execution_mode="auto"`，导致未显式声明时始终走 auto 模式补丁。  
这与当前系统的 interactive 主路径（可等待用户输入并续跑）不一致。

## Goals / Non-Goals

**Goals:**
- 将 Harness start 默认模式切换为 `interactive`。
- 新增 `--auto` 控制参数（位于 engine 前）显式指定 `auto`。
- 保证 `--auto` 不进入 passthrough，不污染引擎原生命令参数。
- 在 resume 时继承启动时的 execution mode，并保持旧 handle 的兼容回退。

**Non-Goals:**
- 不改变主服务 API 的 execution mode 默认值与行为。
- 不改变 adapter 命令 profile 或引擎自身默认参数。
- 不引入 `--interactive` 新参数（本次仅默认 interactive + `--auto`）。

## Decisions

1. CLI 层采用“默认 interactive，`--auto` 覆盖”
- 适用于 legacy 语法与直接语法：
  - `agent_harness start [--auto] <engine> ...`
  - `agent_harness [--auto] <engine> ...`
- rationale:
  - 与当前交互调试诉求一致，且不增加额外必填参数。
- alternative considered:
  - 引入 `--interactive` 与 `--auto` 二选一；被拒绝，因为增加了默认路径复杂度。

2. execution mode 显式进入 Harness 内部请求对象
- 在 `HarnessLaunchRequest` 增加 `execution_mode: Literal["auto","interactive"]`。
- runtime 以该字段驱动：
  - skill patch 注入 mode
  - 审计 meta / handle metadata 记录
- rationale:
  - 防止 mode 在 runtime 内部靠隐式默认推断，导致 resume 漂移。

3. `--auto` 只影响 Harness 控制层，不透传
- CLI 解析后只写入 `HarnessLaunchRequest.execution_mode`。
- passthrough 保持“仅引擎参数”，继续传给 adapter `build_start_command(...)`。
- rationale:
  - 保持 “Harness 控制参数” 与 “引擎参数” 严格隔离。

4. resume 继承模式，旧数据回退 interactive
- start 时将 `execution_mode` 写入 handle metadata。
- resume 时优先读取 handle 的 `execution_mode`，缺失则默认 `interactive`。
- rationale:
  - 新语义要求默认 interactive；历史数据不应导致 resume 失败。
- trade-off:
  - 极少数历史“默认 auto”handle 在缺字段情况下会按 interactive 恢复；该变化可接受且符合新默认。

## Risks / Trade-offs

- [Risk] 现有自动化脚本依赖 Harness 默认 auto 行为  
  → Mitigation: 在文档与错误提示中明确 BREAKING 变更，并给出 `--auto` 迁移方式。

- [Risk] 语法歧义导致 `--auto` 被当作 passthrough  
  → Mitigation: 在 argparse 层把 `--auto` 声明为 harness 顶层参数，并为 legacy/direct 两条解析路径补单测。

- [Risk] resume 模式与首回合模式不一致  
  → Mitigation: handle metadata 持久化 execution mode，并在 resume 读取同一字段。

## Migration Plan

1. 修改 CLI 解析器，增加 `--auto` 并设置默认 interactive。  
2. 扩展 launch/runtime 数据结构，贯通 execution mode。  
3. 扩展 handle metadata 与审计 meta，记录 execution mode。  
4. 更新 Harness 相关单测与文档；验证旧 handle 缺字段回退 interactive。  
5. 发布变更说明：依赖默认 auto 的调用需改为显式 `--auto`。
