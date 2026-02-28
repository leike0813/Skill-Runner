# 核心组件详解 (Core Components)

本文档详细描述 Skill Runner 服务端的核心 Python 类及其职责。

## 1. SkillRegistry (`server/services/skill_registry.py`)
**职责**: 负责技能的发现、加载和元数据管理。

- **扫描 (`scan_skills`)**: 遍历 `skills/` 目录，读取每个子目录下的 `assets/runner.json`。
- **校验**: 确保每个技能具备必要的配置文件和 Schema 定义。
- **Artifact 扫描**: 解析 `output.schema.json`，识别带有 `x-type: "artifact"` 属性的字段，自动将其注册为技能的 Artifact。
- **缓存**: 在内存中维护一份 `Dictionary[skill_id, SkillManifest]` 的映射，供其他组件查询。
- **获取**: 提供 `get_skill(skill_id)` 方法快速检索技能信息。

## 2. WorkspaceManager (`server/services/workspace_manager.py`)
**职责**: 负责“请求/运行实例” (Request/Run) 的生命周期管理和文件系统操作。

- **创建 Request (`create_request`)**:
  - 生成请求目录 `data/requests/<request_id>/`，用于上传与 hashing。
  - 写入 `request.json` 与 `input_manifest.json`。
- **创建 Run (`create_run`)**:
- 生成唯一的 UUID 作为内部 `run_id`。
  - 强校验 `engine` 是否在 `skill.engines` 列表内，不匹配直接抛错。
  - 在 `data/runs/` 下创建对应的目录结构 (`uploads`, `artifacts`, `logs` 等)。
  - 初始化状态为 `queued`。
- **文件处理 (`handle_upload`)**:
  - 接收用户上传的 Zip 二进制流。
  - 解压到请求目录的 `uploads/` 目录。
  - 执行**严格键匹配 (Strict Key-Matching)**：如果压缩包内的文件名与 Schema 定义的 Input Key 一致，则自动关联。
- **路径解析 (`get_run_dir`)**: 提供获取特定 Run 绝对路径的方法，确保路径安全。

## 3. JobOrchestrator (`server/services/job_orchestrator.py`)
**职责**: 任务调度的核心中枢，协调各个组件完成任务执行。

- **流程控制 (`run_job`)**:
  1. 调用 `SkillRegistry` 获取技能定义。
  2. 验证当前 Run 的状态。
  3. **输入校验**: 使用 `SchemaValidator` 分别验证 `input` (files) 和 `parameter` (values)。
  4. **适配器选择**: 根据请求中的 `engine` 参数选择对应的适配器 (如 `gemini` / `codex` / `iflow` / `opencode`)。
  5. 调用对应适配器 (`Adapter.run`) 执行实际任务。
  6. 捕获异常并更新 Run 状态 (SUCCESS/FAILURE)。

## 4. GeminiAdapter (`server/adapters/gemini_adapter.py`)
**职责**: Gemini CLI 执行适配器。

- **上下文构建**: 解析文件输入和参数。
- **Prompt 渲染**: 使用 `server/assets/templates/gemini_default.j2` 模板。
- **CLI 执行**: 调用 `gemini` 命令。

## 5. CodexAdapter (`server/adapters/codex_adapter.py`)
**职责**: Codex CLI 执行适配器，支持非交互式指令执行。

- **配置融合 (Config Fusion)**: 
  - 结合 `ENGINE_DEFAULT` (`server/assets/configs/codex/default.toml`)、`SKILL_DEFAULTS` (`assets/codex_config.toml`)、`RUNTIME_CONFIG`（API 请求）和 `ENFORCED_CONFIG`（系统强制配置）。
  - 动态生成/更新 `~/.codex/config.toml` 中的 `skill-runner` Profile。
- **CLI 执行**: 调用 `codex exec` 命令。

## 6. CodexConfigManager (`server/services/codex_config_manager.py`)
**职责**: 专门管理 Codex 的 TOML 配置文件。

- **Profile 注入**: 安全地读写 `config.toml`，保留原有注释。
- **Schema 校验**: 使用 JSON Schema 验证最终生成的配置是否合法。

## 7. Configuration System (YACS)
**职责**: 全局配置管理。

- **核心定义**: `server/core_config.py` 定义默认配置结构。
- **单例访问**: `server/config.py` 提供全局 `config` 对象。
- **环境感知**: 优先读取环境变量 (如 `SKILL_RUNNER_DATA_DIR`)。



## 8. SchemaValidator (`server/services/schema_validator.py`)
**职责**: 统一的 JSON 数据校验服务。

- 提供 `validate_schema(data, schema_type)` 方法。
- 支持分离验证 `input` 和 `parameter` 两种不同的 Schema。
- 处理 JSON Schema 验证异常并返回可读的错误信息。

## 9. IFlowAdapter (`server/adapters/iflow_adapter.py`)
**职责**: iFlow CLI 执行适配器，支持 Agentic 模式执行。

- **配置生成**: 
  - 生成 `.iflow/settings.json`。
  - 融合 `engine_default -> skill default -> runtime options -> iflow_config -> enforced`。
  - 智能过滤非配置参数（如 runtime 控制开关）。
- **环境隔离**:
  - 将技能复制到 `.iflow/skills/{id}` 以符合 iFlow 工作区标准。
- **执行**:
  - 调用 `iflow` 命令，自动注入 Prompt Template。
  - 解析 stdout 中的 JSON 结果块。

**注意**: 由于iFlow CLI目前不支持JSON流输出且对非交互模式支持较差，暂时不建议使用iflow引擎。

## 10. OpencodeAdapter (`server/adapters/opencode_adapter.py`)
**职责**: OpenCode CLI 执行适配器，支持 `run --format json` 与 session 续跑。

- **配置生成**:
  - 写入运行目录根 `opencode.json`（项目级配置）。
  - 融合 `engine_default -> skill default -> runtime opencode_config -> enforced`。
  - 按执行模式注入 `permission.question`：`auto=deny`，`interactive=allow`。
- **环境隔离**:
  - 将技能复制到 `.opencode/skills/{id}`。
- **执行命令**:
  - 首轮：`opencode run --format json --model <provider/model> <prompt>`
  - 续跑：`opencode run --session=<session_id> --format json --model <provider/model> <message>`
- **流解析**:
  - 解析 OpenCode NDJSON（如 `step_start/tool_use/text/step_finish/error`），提取会话 ID 与最终助手文本。
