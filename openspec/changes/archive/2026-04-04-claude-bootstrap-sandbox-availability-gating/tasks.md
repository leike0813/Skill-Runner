## 1. OpenSpec

- [x] 1.1 创建 `claude-bootstrap-sandbox-availability-gating` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Bootstrap Probe

- [x] 2.1 在 `AgentCliManager.ensure_layout()` 中增加 Claude sandbox smoke probe
- [x] 2.2 将 probe 结果持久化到 Claude bootstrap sidecar
- [x] 2.3 将 Claude sandbox 状态读取改为基于 bootstrap probe sidecar

## 3. Headless Claude Gating

- [x] 3.1 基于 sidecar 控制 Claude headless `settings.json` 的 `sandbox.enabled`
- [x] 3.2 基于 sidecar 调整 Claude 默认 prompt / fallback 文案

## 4. Validation

- [x] 4.1 更新 AgentCliManager / Claude config / prompt 回归测试
- [x] 4.2 运行目标 pytest
- [x] 4.3 运行目标 mypy
