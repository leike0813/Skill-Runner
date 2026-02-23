# 执行流程逻辑 (Execution Flow)

本文档描述一个典型的 Skill 执行请求在系统内部的流转过程。

## 阶段一：初始化与上传 (Setup & Upload)

1. **Client -> API**: 发送 `POST /v1/jobs` 创建请求。
   - Payload: 包含 `skill_id` 和 `parameter` JSON (仅配置值)。
2. **WorkspaceManager**:
   - 创建 `data/requests/<request_id>/` 目录。
   - 返回 `request_id`。
3. **Client -> API**: (可选) 发送 `POST /v1/jobs/<request_id>/upload` 上传文件。
   - Payload: Zip 文件。
4. **WorkspaceManager**:
   - 解压 Zip 到 `data/requests/<request_id>/uploads/`。
   - 生成 `input_manifest.json` 并计算 cache key。
   - 缓存仅在 `execution_mode=auto` 且 `no_cache!=true` 时启用；`interactive` 不读不写缓存。
   - 临时 skill 链路的 cache key 额外包含上传 skill 压缩包整体哈希。
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

**Selected Adapter (Gemini/Codex)** 接管控制权：

1. **环境准备**:
   - 将技能的 `assets/` 和 `SKILL.md` 复制/安装到运行目录 `.gemini/skills/` 下，确保执行环境隔离。
2. **输入解析 (Input Resolution)**:
   - 遍历 `input` Schema 的所有键。
   - **Strict Key-Matching**: 检查 `uploads/` 目录下是否存在同名文件。
     - **若存在**: 计算绝对路径并注入上下文。
     - **若不存在**: 抛出错误 (MissingFileError)。禁止使用 JSON 中的字符串值作为回退。
3. **上下文构建 (Context Building)**:
   - `input_ctx`: 包含解析后的文件绝对路径。
   - `param_ctx`: 包含纯数值参数。
4. **Prompt 生成 (Adapter Dependent)**:
   - **Gemini**: 加载 Jinja2 模板，注入上下文，渲染为 `prompt.txt`。
   - **Codex**: 融合配置，构造 CLI 参数。

## 阶段四：执行 (Execution)

1. **Command Construction**:
   - Gemini: `gemini --yolo <prompt>`
   - Codex: `codex exec --full-auto --skip-git-repo-check --json -p skill-runner <prompt>`（不支持 landlock 时回退 `--yolo`）
   - 设置工作目录为 `data/runs/<uuid>/`。
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
