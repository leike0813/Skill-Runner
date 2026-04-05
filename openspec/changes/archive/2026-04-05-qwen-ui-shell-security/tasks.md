## Tasks

### Phase 1: 创建 UI Shell 配置文件

- [x] 创建 `server/engines/qwen/config/ui_shell_default.json`
- [x] 创建 `server/engines/qwen/config/ui_shell_enforced.json`
- [x] 验证 JSON schema 引用正确

### Phase 2: 更新 Schema

- [x] 在 `qwen_config_schema.json` 中添加 `tools` 定义
- [x] 在 `qwen_config_schema.json` 中添加 `permissions` 定义
- [x] 在 `qwen_config_schema.json` 中添加 `sandbox` 定义

### Phase 3: 更新 Adapter Profile

- [x] 更新 `adapter_profile.json` 的 `ui_shell.config_assets`
- [x] 设置 `target_relpath` 为 `.qwen/settings.json`
- [x] 设置 `default_path` 和 `enforced_path`
- [x] 设置 `settings_schema_path`

### Phase 4: 验证和测试

- [x] 运行 mypy 类型检查
- [x] 运行 `pytest tests/unit/test_adapter_command_profiles.py -v`
- [x] 检查配置文件是否被正确加载

### Phase 5: OpenSpec 文档

- [x] 创建 `specs/qwen-ui-shell-security/spec.md`
- [x] 更新 `.openspec.yaml`（如果需要）
