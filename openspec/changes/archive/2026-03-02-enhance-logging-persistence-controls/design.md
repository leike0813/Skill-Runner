## Context

当前 `server/logging_config.py` 使用 `RotatingFileHandler` 与环境变量直接解析，策略分散且只支持大小轮换。项目需要一个可持续运维的全局应用日志策略：配置统一、按天轮换、目录总配额与故障降级。

## Goals / Non-Goals

**Goals**
- 建立 `core_config` 驱动的日志配置域，支持环境变量覆盖。
- 将全局应用日志切换为按天轮换，并支持保留天数配置。
- 增加 `data/logs` 目录总配额控制（最旧归档优先淘汰）。
- 提供文本默认 + JSON 可选格式，保持默认兼容。
- 保障 `setup_logging()` 幂等，不重复添加 handlers。

**Non-Goals**
- 不改 `run_dir/logs/*` 与 `.audit/*` 产物日志策略。
- 不改 HTTP API、runtime schema/invariants、状态机语义。
- 不引入第三方日志框架（维持 stdlib logging）。

## Decisions

### 1) 配置策略：`core_config` 默认 + 环境覆盖
- Decision: 在 `SYSTEM.LOGGING` 增加日志策略节点；`setup_logging()` 运行时再读取环境变量覆盖。
- Rationale: 保留中心化配置与部署灵活性，避免单一来源僵化。

### 2) 轮换策略：按天滚动
- Decision: 使用 `TimedRotatingFileHandler(when=\"midnight\", interval=1)`，保留天数映射到 `backupCount`。
- Rationale: 与运维周期一致，便于排障和容量预测。

### 3) 配额策略：目录总量限制 + 最旧归档淘汰
- Decision: 在 `data/logs` 内对“当前日志文件 + 同名前缀归档”统计总量；超限时按 mtime 删除最旧归档，永不删除 active 文件。
- Rationale: 在不影响实时写入的前提下控制磁盘占用，且不误删当前写入目标。

### 4) 格式策略：文本默认，JSON 可选
- Decision: 默认 `logging.Formatter` 文本格式，`LOG_FORMAT=json` 时启用 JSON formatter。
- Rationale: 保持现有消费习惯，逐步支持结构化日志接入。

### 5) 故障降级：stream-only 并记录结构化告警
- Decision: 文件 handler 初始化异常时继续安装 stream handler，并输出包含 `component/action/error_type/fallback` 的 warning。
- Rationale: 文件系统异常不应阻断服务可用性。

## Risks / Trade-offs

- [Risk] 严格移除 `LOG_MAX_BYTES` 可能影响旧部署脚本。
  - Mitigation: 文档明确迁移到 `LOG_RETENTION_DAYS` + `LOG_DIR_MAX_BYTES`。
- [Risk] 配额策略若作用范围过大可能清理非目标日志。
  - Mitigation: 仅清理当前应用日志 basename 前缀归档。
- [Risk] 根 logger 在测试环境下可能已有 handler。
  - Mitigation: 通过显式标记保证 `setup_logging()` 幂等，不依赖“handlers 是否为空”。

## Migration Plan

1. 在 `core_config` 增加 `SYSTEM.LOGGING` 默认值与环境覆盖映射。
2. 重构 `logging_config`：格式器、timed handler、配额清理、降级逻辑、幂等标记。
3. 新增测试：配置安装、幂等、JSON 输出、配额清理、降级路径。
4. 更新文档中的日志变量说明与示例命令。
5. 执行 pytest + mypy 验证。

## Open Questions

- 无。该 change 的实现决策已锁定。

