# Skill Runner

Skill Runner 是一个轻量级的 REST 服务，用于统一封装 Codex、Gemini CLI、iFlow CLI 等成熟 Agent 工具，
以“Skill”协议提供可复用、可验证的自动化能力。

## 功能概览

- 多引擎执行：Codex / Gemini CLI / iFlow CLI
- Skill 协议：`runner.json` + `SKILL.md` + 输入/参数/输出 schema
- 执行隔离：每次 run 独立工作目录
- 结构化输出：JSON 结果 + artifacts + bundle
- 缓存与复用：同输入同参数可复用结果

## 构建与启动（容器）

建议先在宿主机准备挂载目录，避免容器创建导致权限问题：
```
mkdir -p skills agent_config data
```
> `data` 目录可选：仅在需要持久化运行记录/调试时挂载。

构建镜像：
```
docker build -t skill-runner:local .
```

使用 Compose 启动（推荐）：
```
docker compose up --build
```

默认端口：`http://localhost:8000/v1`

> 详细容器化说明请见 `docs/containerization.md`。

## 本地运行（非容器）

推荐使用 `uv` 管理环境：
```
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

可选环境变量：
- `SKILL_RUNNER_DATA_DIR`：运行数据目录（默认 `data/`）

## API 示例（关键）

列出技能：
```
curl -sS http://localhost:8000/v1/skills
```

列出引擎与模型：
```
curl -sS http://localhost:8000/v1/engines
curl -sS http://localhost:8000/v1/engines/gemini/models
```

创建任务：
```
curl -sS -X POST http://localhost:8000/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "demo-bible-verse",
    "engine": "gemini",
    "parameter": { "language": "en" },
    "model": "gemini-3-pro-preview",
    "runtime_options": { "no_cache": false, "debug": false }
  }'
```

上传文件（zip）：
```
curl -sS -X POST http://localhost:8000/v1/jobs/<request_id>/upload \
  -F "file=@inputs.zip"
```

查询状态与结果：
```
curl -sS http://localhost:8000/v1/jobs/<request_id>
curl -sS http://localhost:8000/v1/jobs/<request_id>/result
```

获取产物清单与 bundle：
```
curl -sS http://localhost:8000/v1/jobs/<request_id>/artifacts
curl -sS -o run_bundle.zip http://localhost:8000/v1/jobs/<request_id>/bundle
```

Codex 的 `model` 格式：
- `model_name@reasoning_effort`，例如 `gpt-5.2-codex@high`

完整接口说明见 `docs/api_reference.md`。

## 架构概览（简述）

核心组件：
- Skill Registry：扫描并加载 `skills/`
- Workspace Manager：准备 run 目录结构
- Job Orchestrator：校验输入/输出、执行流程、打包结果
- Engine Adapters：对接 Codex / Gemini / iFlow CLI

执行流程：
1) POST /v1/jobs  
2) 可选上传 inputs.zip  
3) 执行引擎 → 产物落盘  
4) 输出校验与 bundle 打包  
5) GET 结果与下载

## Agent 工具登录方式

方式一：进入容器内 TUI 登录
```
docker exec -it <container_id> /bin/bash
```
在容器内运行对应 CLI 登录（会生成凭据文件）。

方式二：在宿主机或其他机器登录后复制凭据

需要的凭据文件：
- Codex: `auth.json`
- Gemini: `google_accounts.json`, `oauth_creds.json`
- iFlow: `iflow_accounts.json`, `oauth_creds.json`

复制到挂载目录：
- `agent_config/codex/`
- `agent_config/gemini/`
- `agent_config/iflow/`

## 支持的 Agent 工具

- Codex CLI (`@openai/codex`)
- Gemini CLI (`@google/gemini-cli`)
- iFlow CLI (`@iflow-ai/iflow-cli`)

---

更多细节请参考 `docs/` 目录。 
