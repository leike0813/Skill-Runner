## 1. OpenSpec artifacts

- [x] 1.1 创建 `introduce-auth-detection-layer` change
- [x] 1.2 补齐 proposal / design / tasks
- [x] 1.3 编写新 capability spec：`auth-detection-layer`
- [x] 1.4 编写 delta specs：`engine-execution-failfast`、`interactive-run-lifecycle`、`engine-adapter-runtime-contract`

## 2. Auth detection core

- [x] 2.1 新增 `server/runtime/auth_detection/types.py` 定义结果、证据和规则类型
- [x] 2.2 新增 rule loader / registry / service，并在启动时完成规则包 schema 校验
- [x] 2.3 新增 rule pack schema 与 `common/codex/gemini/iflow/opencode` YAML 规则文件

## 3. Engine-specific detectors

- [x] 3.1 新增 `codex` detector，输出 combined text 证据
- [x] 3.2 新增 `gemini` detector，输出 combined text 与本地 auth 配置缺失证据
- [x] 3.3 新增 `iflow` detector，输出 oauth 过期/重认证证据
- [x] 3.4 新增 `opencode` detector，提取 provider 结构化错误字段和问题样本信号

## 4. Runtime integration

- [x] 4.1 在 `run_job_lifecycle_service` 中接入 auth detection，顺序早于 generic pending interaction inference
- [x] 4.2 将高置信度命中映射为 `failure_reason=AUTH_REQUIRED` 并阻止 `waiting_user` 推断
- [x] 4.3 将 medium/low 命中保留为审计结果，不改变现有失败/等待态行为
- [x] 4.4 将 `base_execution_adapter` 的旧 regex 判定降级为 legacy fallback

## 5. Audit and observability

- [x] 5.1 在 `.audit/meta.{attempt}.json` 中持久化 `auth_detection`
- [x] 5.2 在 parser diagnostics 中新增 `AUTH_DETECTION_MATCHED` 记录
- [x] 5.3 确保 `RunObservabilityService` 能读取 attempt-level `auth_detection`

## 6. Verification

- [x] 6.1 新增基于 fixture 的 unit tests：loader / codex / gemini / iflow / opencode
- [x] 6.2 新增 lifecycle integration 和 audit persistence 测试
- [x] 6.3 运行指定 pytest 集合
- [x] 6.4 运行 mypy
