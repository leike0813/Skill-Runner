## Context

容器启动链路当前是线性串行：

1. 打印环境摘要  
2. `agent_manager.py --ensure` 安装缺失 CLI  
3. 导入认证凭据  
4. 启动 API  
5. 应用 startup 刷新模型目录（如 opencode）

问题在于第 2 步与第 5 步日志语义不足：失败没有可操作细节，且缺乏统一诊断上下文。

## Goals / Non-Goals

**Goals:**
- 让“安装失败”在日志层面可直接定位（命令、返回码、stderr 摘要、耗时）。  
- 让“模型探测失败”直接给出与安装状态关联的解释。  
- 给出可持久化、可检索的启动诊断工件（不依赖实时终端）。

**Non-Goals:**
- 不改变 agent 安装策略（仍 npm install -g）。  
- 不改变 API/协议语义。  
- 不把启动问题转成服务启动阻断（本 change 仅增强观测）。

## Decisions

### 1) 启动期结构化日志

- 统一采用 `event=<code> key=value...` 风格输出关键启动事件。  
- 关键事件：`bootstrap.start` / `agent.ensure.start` / `agent.install.result` / `catalog.refresh.result` / `bootstrap.done`。  
- 每条事件包含 `phase`, `engine?`, `outcome`, `duration_ms?`, `exit_code?`。

### 2) 双写策略（控制台 + 文件）

- 启动阶段日志继续输出到容器 stdout。  
- 同步写入 `${SKILL_RUNNER_DATA_DIR}/logs/bootstrap.log`（轮转）。  
- 生成 `${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json`，聚合每个 engine 的 ensure/install 结果。

### 3) 安装失败摘要与脱敏

- 记录失败命令（argv）与返回码。  
- `stderr` 做截断摘要（例如前后各 N 行）并做敏感字段脱敏。  
- 保留可关联的“下一步建议”字段（例如检查网络、npm registry、权限、代理）。

### 4) opencode 模型探测错误增强

- 当 `opencode CLI not found` 时，日志追加关联建议：
  - 检查 `runs.db` 的 `engine_status_cache` 表中 `opencode.present`
  - 检查 `agent_bootstrap_report.json` 对应安装失败详情

## Migration Plan

1. 扩展 `agent_manager.py` 的 ensure 输出模型（结构化结果）。  
2. entrypoint 接入启动日志双写与诊断报告写入。  
3. 补充 opencode catalog 失败关联日志。  
4. 更新容器文档排障章节。  
5. 加测试覆盖日志字段与报告结构。

## Risks / Trade-offs

- [Risk] 启动日志过多  
  - Mitigation: 仅对关键阶段打点；stderr 摘要截断。

- [Risk] 日志含敏感信息  
  - Mitigation: 对 token/secret 模式做掩码，禁止明文输出。
