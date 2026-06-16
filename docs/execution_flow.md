# 执行流程逻辑 (Execution Flow)

本文档描述一个典型的 Skill 执行请求在系统内部的流转过程。

## Workspace 复用

串行多 skill 工作流可以在后续 `POST /v1/jobs` 请求中提交 `runtime_options.workspace.mode="reuse"` 和前序成功请求的 `request_id`。后续请求保留独立 logical `run_id`，但复用前序请求的物理 workspace。Runner-owned 文件写入 run record 暴露的 `resultJsonPath` 与 `inputManifestPath`，调用方不应拼接 `result/result.json`。

## Run-local Env 注入

客户端可以通过 `runtime_options.env` 为单次 run 注入局部环境变量。API 创建请求时会先校验 env，再将 raw value 写入 `data/run_secrets/<request_id>.env.json`，普通 request record 与 input manifest 只保存 redacted 投影。执行 attempt 准备阶段从 vault 重新加载 raw env，作为内部 `__runtime_env` 传给 adapter；adapter 只把它叠加到当前 subprocess env，不修改全局 `os.environ`。

## 阶段一：初始化与上传 (Setup & Upload)

1. **Client -> API**: 发送 `POST /v1/jobs` 创建请求。
   - Payload: 包含 `skill_id` 和 `parameter` JSON (仅配置值)。
2. **WorkspaceManager**:
   - 创建 `data/requests/<request_id>/` 目录。
   - 返回 `request_id`。
   - 在临时 skill 或需要上传的请求中，此时可能尚未绑定 `run_id`。客户端可以立即读取 `GET /v1/jobs/{request_id}`，响应为 `queued` 且 `observability_ready=false`；`/events/history` 与 `/chat/history` 返回空历史，实时 SSE 只返回 pre-observable keepalive。
3. **Client -> API**: (可选) 发送 `POST /v1/jobs/<request_id>/upload` 上传文件。
   - Payload: Zip 文件。
4. **WorkspaceManager**:
   - 解压 Zip 到 `data/requests/<request_id>/uploads/`。
   - 生成 `input_manifest.json` 并计算 cache key v2。
   - 缓存仅在 `execution_mode=auto` 且 `no_cache!=true` 时启用；`interactive` 不读不写缓存。
   - cache key v2 统一包含 skill id、engine、规范化 `skill_package_hash`、参数、engine options、上传文件清单哈希和 inline input 哈希。
   - `runtime_options.env` 不进入 cache key；若 env 会影响输出，调用方需设置 `no_cache=true`。
   - 已安装 skill 与临时上传 skill 使用同一套 `skill_package_hash` 口径；临时上传包会缓存未 patch 的规范化 snapshot，默认 30 天滑动 TTL。
   - 命中缓存则将缓存的 run 绑定到 `request_id`；未命中则创建 `data/runs/<run_id>/`。

## 阶段二：任务调度 (Orchestration)

1. **Client -> API**: 上传完成即触发执行（服务端自动触发）。
2. **JobOrchestrator**:
   - `get_skill(skill_id)`: 获取技能清单。
   - **Engine Gate**:
     - `engine` 必须包含在 `skill.engines` 中（由 WorkspaceManager 兜底拦截）。
   - **Schema Splitting**: 
     - 识别 `runner.json` 中的 `input` (文件) 和 `parameter` (数值) Schema。
   - **Validation**:
     - 验证传入的 `parameter` JSON 是否符合 `parameter` Schema。
     - 检查 `uploads/` 目录下的文件是否符合 `input` Schema 的要求 (存在性检查)。

## 阶段三：适配与准备 (Adaptation)

**Selected Adapter (Gemini/Codex/IFlow/OpenCode)** 接管控制权：

1. **环境准备**:
   - 将技能的 `assets/` 和 `SKILL.md` 复制/安装到运行目录 `.<engine>/skills/` 下（如 `.gemini/.codex/.qwen/.opencode`），确保执行环境隔离。
   - 若 request 声明了 `runtime_options.env`，从 secret vault 加载 raw env；vault 缺失时 run 失败并返回 `RUNTIME_ENV_SECRET_MISSING`。
2. **输入解析 (Input Resolution)**:
   - 遍历 `input` Schema 的所有键。
   - **声明式 file path 解析**: 若请求体 `input.<key>` 为 file 字段提供了 `uploads/` 相对路径，则优先按该路径解析。
   - **兼容回退**: 若请求体未显式提供 file 路径，再回退到旧的 strict key-matching（检查 `uploads/<key>` 是否存在）。
   - **若最终未命中**: 对 required file 字段抛出缺文件错误。
3. **上下文构建 (Context Building)**:
   - `input_ctx`: 包含解析后的文件绝对路径。
   - `param_ctx`: 包含纯数值参数。
4. **Prompt 生成 (Adapter Dependent)**:
   - **Gemini**: 加载 Jinja2 模板，注入上下文，渲染为 `prompt.txt`。
   - **Codex**: 融合 `engine_default -> skill default -> runtime -> enforced`，再构造 CLI 参数。
   - **Gemini / Qwen / OpenCode**: 在运行目录写入项目级配置，统一遵循 `engine_default -> skill default -> runtime -> enforced` 合成顺序。
   - **OpenCode 特例**: 额外按执行模式写入 `permission.question`（`auto=deny`，`interactive=allow`）。

## 阶段四：执行 (Execution)

1. **Command Construction**:
   - Gemini: `gemini --yolo <prompt>`
   - Codex: `codex exec --full-auto --skip-git-repo-check --json -p skill-runner <prompt>`（不支持 landlock 时回退 `--yolo`）
   - OpenCode: `opencode run --format json --model <provider/model> <prompt>`
   - 设置工作目录为 `data/runs/<uuid>/`。
   - 如果存在 run-local env，dependency probe、uv wrapper 与最终 adapter subprocess 使用同一份叠加后的 env。
   > **注意**: 以上命令行示例为简化展示。实际 CLI 参数由各引擎的 `adapter_profile.json` 中 `command_defaults` 驱动，并由引擎 `CommandBuilder` 动态构建。
2. **Run Folder Trust 生命周期（Codex/Gemini）**:
   - 在真正调用 CLI 前，服务会将本次 `run_dir` 写入全局 trust 配置。
     - Codex: `~/.codex/config.toml` -> `projects."<run_dir>".trust_level = "trusted"`
     - Gemini: `~/.gemini/trustedFolders.json` -> `"<run_dir>": "TRUST_FOLDER"`
   - CLI 执行结束后（无论成功/失败），在 `finally` 路径删除该 `run_dir` trust 记录。
   - trust 回收失败只记录 warning，不会覆盖本次 run 的最终状态。
3. **Subprocess**:
   - 启动异步子进程。
   - 实时流式读取 `stdout` 和 `stderr` 并写入 `logs/` 目录。
4. **Completion**:
   - 等待进程结束。
   - 解析最终输出 (JSON)。
   - 更新 Run 状态为 `succeeded` / `failed`。
   - 生成 bundle（debug/非 debug）。

## 阶段五：周期补偿清理 (Maintenance)

- 定时清理任务会在清理历史 run 的同时，扫描活动 run 列表并执行 stale trust 清理。
- 仅清理 `runs` 根目录下、且不在活动集合（`queued/running`）中的 Codex/Gemini trust 条目。
- 定时清理也会移除超过滑动 TTL 的临时 skill 包缓存 snapshot；TTL 内再次使用同一规范化包 hash 会刷新过期时间。
