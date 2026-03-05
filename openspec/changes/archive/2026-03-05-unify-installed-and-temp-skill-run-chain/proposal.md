# Proposal: unify-installed-and-temp-skill-run-chain

## 背景

当前正式 Skill 与临时 Skill 在 request 持久化、创建入口、观测入口仍有并行双链路，主要表现为：

- `/v1/jobs/*` 与 `/v1/temp-skill-runs/*` 双 API 入口；
- `run_store.requests` 与 `temp_skill_runs` 双 request 存储；
- e2e 客户端 `run_source` 双路径观测；
- request 目录文件落盘与 DB 持久化并存。

这些分叉会显著增加行为漂移风险，特别是在互动回复、鉴权恢复、观测回放的一致性上。

## 目标

一次性收口为单链路：

1. 统一 `/v1/jobs` 入口承载 installed + temp_upload；
2. request 持久化统一到 `run_store.requests`；
3. request 目录退役，上传改为请求内临时 staging；
4. 观测/回放删除 `run_source` 分叉；
5. 删除 temp 生命周期清理残留；
6. 保留 cache 语义隔离（installed/temp 分开命中空间）。

## 非目标

- 不改 FCMP/RASP 协议与状态机合同；
- 不改 run 目录作为执行工作目录的地位；
- 不改变 engine 侧执行协议。

## 成功标准

1. `/v1/temp-skill-runs/*` 完全移除；
2. request 目录不再创建；
3. e2e 与管理端观测均走 `/v1/jobs/*`；
4. temp 与 installed cache 互不命中；
5. 互动/鉴权/恢复链路在单入口下保持可用；
6. `temp_upload` 在 `/v1/jobs/{request_id}/upload` 后必须可创建 run，不得因 installed registry 校验失败而中断。
