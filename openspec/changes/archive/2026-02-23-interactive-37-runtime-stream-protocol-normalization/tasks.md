## 1. 运行时协议与事件总线基建

- [x] 1.1 在 `server/models.py` 增加 RASP/FCMP 事件模型与枚举（category/type/source/correlation/raw_ref）
- [x] 1.2 在运行链路中引入统一 `seq/cursor` 语义，保证同一 run 下 `seq` 全局严格递增
- [x] 1.3 在 `server/services/job_orchestrator.py` 中接入运行时事件发布点（lifecycle/interaction/error）
- [x] 1.4 在 run 目录新增规范化事件落盘（`events.jsonl`、`parser_diagnostics.jsonl`）并与现有日志并存
- [x] 1.5 在事件模型中增加 `attempt_number` 与规范化 `raw_ref`（`stream/byte_from/byte_to/encoding`）

## 2. 审计采集与流重建规范化

- [x] 2.1 规范 run attempt 审计文件命名与写入流程（interactive: 初始 `N=1`，每次 reply 递增；auto: 固定 `N=1`）
- [x] 2.2 实现或抽象 stdout/stderr 重建流程，保证可基于运行期 trace/证据重放且不落盘 `fd-trace`
- [x] 2.3 增加 fs 快照与 `fs-diff` 产出逻辑，并排除审计目录噪声
- [x] 2.4 实现统一 completion 判定链路（done signal > process fail > done marker > terminal signal > unknown）
- [x] 2.5 在 `meta.N.json` 增加重建摘要字段（`reconstruction_used/stdout_chunks/stderr_chunks/reconstruction_error`）

## 3. 按引擎 parser profile 解析与诊断

- [x] 3.1 新增 parser profile 框架（`codex_ndjson/gemini_json/iflow_text/opencode_ndjson`）
- [x] 3.2 实现 codex/opencode 的 NDJSON 解析、PTY 回退与去重策略
- [x] 3.3 实现 gemini 的 stderr JSON 优先解析与 stdout 噪声诊断映射
- [x] 3.4 实现 iflow 的文本/块/正则分层解析与低置信度降级
- [x] 3.5 统一 raw 兜底策略：解析失败不丢数据，必须发 `diagnostic.warning`
- [x] 3.6 补齐确定性容错链路：NDJSON 行级失败、Gemini fenced JSON 提取、iFlow 无结构块降级

## 4. SSE、前端协议与转译流程

- [x] 4.1 扩展 `server/services/run_observability.py` 与相关 router，提供 `run_event`（RASP）输出
- [x] 4.2 新增 RASP->FCMP 转译器，输出 `conversation.started/assistant.message.final/user.input.required/conversation.completed/conversation.failed/diagnostic.warning`
- [x] 4.3 改造 run 观测 UI（管理页与 e2e 客户端）优先消费 FCMP，并保留原始日志对照入口
- [x] 4.4 完成 cursor 重连一致性实现与前端续传联调
- [x] 4.5 增加前端低置信度与诊断分区展示约束（主对话与诊断视图分离）
- [x] 4.6 增加历史回放 API（支持 `from_seq/to_seq` 与 `from_ts/to_ts` 区间拉取）
- [x] 4.7 在 run 观测 UI 中增加事件关联关系视图，并支持从关系节点回跳事件详情
- [x] 4.8 在 RASP->FCMP 转译层实现 raw 回显抑制（默认阈值 `>=3` 行），并输出 `RAW_DUPLICATE_SUPPRESSED`

## 5. skill patch 运行时注入规范化

- [x] 5.1 在 `server/services/skill_patcher.py` 中改造 completion contract 注入：从 Markdown 配置文件加载文案（含 done marker 规则）
- [x] 5.2 保持补丁分层：artifact 重定向补丁与 execution_mode 补丁分离
- [x] 5.3 规范 interactive 模式注入语义：允许 ask_user、未完成不得提前 done
- [x] 5.4 增加 patch 幂等保护，避免重复注入和冲突段落
- [x] 5.5 为 completion contract 增加配置文件存在性与可读性校验（缺失时 fail-fast）
- [x] 5.6 强制 completion marker 仅支持大写 `__SKILL_DONE__`，并实现“单轮首个 marker 生效”规则

## 6. 测试、文档与回归

- [x] 6.1 新增 parser fixture 测试：覆盖 codex/gemini/iflow/opencode 的解析与终态判定
- [x] 6.2 新增 SSE 协议测试：`run_event`、cursor 恢复与诊断事件
- [x] 6.3 新增 FCMP 转译测试：事件映射、终态互斥、`user.input.required` 硬判规则
- [x] 6.4 新增 skill patch 测试：completion contract 注入、幂等、interactive 约束
- [x] 6.5 新增配置驱动 patch 测试：Markdown 配置读取、缺失配置失败路径
- [x] 6.6 新增 completion 冲突测试：done marker 与进程非零退出冲突时判定 `interrupted`
- [x] 6.7 增加协议链路指标采集与断言（parser 命中率/fallback/unknown）
- [x] 6.8 更新 `docs/api_reference.md`、`docs/dev_guide.md` 与新增协议文档（RASP/FCMP/审计规范）
- [x] 6.9 运行全量单元测试并修复回归，确保变更可验收
- [x] 6.10 新增历史回放 API 测试（seq 区间、时间区间、与 SSE 衔接无缺口）
- [x] 6.11 新增 UI 联调测试：`raw_ref` 回跳与事件关联视图可用性
- [x] 6.12 新增 FCMP 抑制测试：重复 raw 回显块被抑制、非重复 raw 保留、RASP 原始记录不受影响
