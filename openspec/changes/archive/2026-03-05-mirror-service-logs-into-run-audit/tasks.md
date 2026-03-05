## 1. OpenSpec Artifacts

- [x] 1.1 完成 proposal/design/tasks 与 delta specs，明确 run 级服务日志镜像合同。

## 2. Runtime Logging Context

- [x] 2.1 新增 `contextvars + LogRecordFactory`，为日志注入 `run_id/request_id/attempt_number`。
- [x] 2.2 在 logging setup 中安装该 factory，保持幂等。

## 3. Run Attempt Mirror

- [x] 3.1 新增 `RunServiceLogMirrorSession`，支持 run-scope（全集）与 attempt-scope（分片）镜像。
- [x] 3.2 在 `run_job` attempt 生命周期接入双镜像会话（`service.run.log` + `service.<attempt>.log`），保证所有退出路径关闭 handler。
- [x] 3.3 在 create-run / upload / interaction / auth status 等 attempt 外编排路径接入 run-scope 镜像。

## 4. Audit Contract

- [x] 4.1 在 `RunAuditContract` 增加 `run_service_log_path` 与 `service_log_path`。
- [x] 4.2 在 run/attempt 审计骨架初始化中预创建 `service.run.log` 与 `service.<attempt>.log`。

## 5. Tests and Docs

- [x] 5.1 新增日志上下文、镜像过滤/轮转、审计骨架的单测。
- [x] 5.2 更新 `docs/run_artifacts.md` 的审计工件说明（全集 + 分片）。
- [x] 5.3 在 attempt 关键路径补充结构化 `logger.info`，确保成功路径可审计。
