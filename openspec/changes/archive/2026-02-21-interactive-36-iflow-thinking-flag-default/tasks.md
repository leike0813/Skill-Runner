## 1. iFlow 参数注入实现

- [x] 1.1 在 `server/adapters/iflow_adapter.py` 的非 resume 命令构造中默认追加 `--thinking`
- [x] 1.2 在 `server/adapters/iflow_adapter.py` 的 resume 命令构造中默认追加 `--thinking`
- [x] 1.3 确认 `auto` 与 `interactive` 两种模式下参数行为一致（均包含 `--thinking`）

## 2. 测试与验证

- [x] 2.1 更新 `tests/unit/test_iflow_adapter.py`，覆盖非 resume 与 resume 场景均包含 `--thinking`
- [x] 2.2 运行 `pytest tests/unit/test_iflow_adapter.py`
- [x] 2.3 运行 `mypy server`

## 3. 文档与归档准备

- [x] 3.1 核对 `interactive-engine-turn-protocol` 变更与实现一致
- [x] 3.2 执行 change verify，确认进入 apply-ready
