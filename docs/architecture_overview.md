# 架构总览 (Architecture Overview)

## 简介
Skill Runner 是一个专为 AI Agent 设计的技能执行框架。它允许 LLM（如 Gemini）通过标准化的协议发现、配置并执行本地或通过 MCP (Model Context Protocol) 定义的各种“技能” (Skills)。该系统旨在解决复杂任务自动化、本地环境交互以及工具链集成的需求。

## 核心设计理念
1.  **标准化 (Standardization)**: 所有技能遵循统一的定义规范 (`runner.json`, `SKILL.md`) 和输入/输出协议。
2.  **隔离性 (Isolation)**: 每次技能执行 (Run) 都在独立的工作区目录中进行，互不干扰。
3.  **可扩展性 (Extensibility)**: 支持多种对接入 (Native, Docker, MCP)，目前核心支持基于 Gemini CLI 和 Codex CLI 的 Native 执行。
4.  **无状态与有状态结合**: 服务本身无状态，但通过文件系统 (`data/runs`) 持久化执行上下文。

## 系统架构图 (概念)

```mermaid
graph TD
    Client[客户端/LLM] -->|HTTP Request| Server[Skill Runner Server]
    
    subgraph Server
        API[FastAPI Interface]
        Orchestrator[Job Orchestrator]
        Registry[Skill Registry]
        Workspace[Workspace Manager]
        GeminiAdapter[Gemini Adapter]
        CodexAdapter[Codex Adapter]
    end
    
    subgraph Storage [文件系统]
        SkillsDir[skills/ (技能定义)]
        RunsDir[data/runs/ (执行沙箱)]
    end
    
    subgraph External [外部执行器]
        GeminiCLI[Gemini CLI]
        CodexCLI[Codex CLI]
    end

    API --> Orchestrator
    Orchestrator --> Registry
    Orchestrator --> Workspace
    Orchestrator --> GeminiAdapter
    Orchestrator --> CodexAdapter
    
    Registry --> SkillsDir
    Workspace --> RunsDir
    GeminiAdapter --> GeminiCLI
    CodexAdapter --> CodexCLI
    GeminiCLI --> RunsDir
    CodexCLI --> RunsDir
```

## 目录结构约定

系统的核心逻辑高度依赖于文件系统的目录结构，主要分为两部分：

### 1. 技能库 (`skills/`)
存放所有可用技能的定义。每个技能一个子目录，目录名为 `skill_id`。

```text
skills/
├── demo-prime-number/       # 技能 ID
│   ├── assets/
│   │   ├── runner.json      # 核心配置文件：定义元数据、Schema、Prompt等
│   │   ├── input.schema.json # 文件输入定义
│   │   ├── parameter.schema.json # 参数定义
│   │   └── gemini_settings.json # 默认配置
│   ├── SKILL.md             # 技能的 Prompt 模板/核心指令
│   └── ...
└── ...
```

### 2. 运行数据 (`data/runs/`)
存放每次执行的实例数据。

```text
data/runs/
├── <run_id>/   (内部)
│   ├── uploads/             # 用户上传的文件存放于此
│   ├── artifacts/           # 技能生成的产物
│   ├── logs/                # 执行日志 (stdout, stderr, prompt)
│   ├── bundle/              # 运行结果打包 (zip + manifest)
│   ├── .gemini/             # 运行时临时目录
│   └── ...

data/requests/
└── <request_id>/
    ├── uploads/             # 请求阶段上传文件
    ├── request.json         # 请求原始参数
    └── input_manifest.json  # 输入文件哈希清单
```

## 技术栈
- **语言**: Python 3.11+
- **Web 框架**: FastAPI
- **模板引擎**: Jinja2 (用于 Prompt 渲染)
- **校验**: JSON Schema (jsonschema)
- **底层 CLI**: 
  - **Gemini CLI**: Node.js based (通过 `subprocess` 调用)
  - **Codex CLI**: Python based (通过 `subprocess` 调用)

## 日志配置
日志默认输出到终端与 `data/logs/`，可通过环境变量控制：
- `LOG_LEVEL`: 日志级别（默认 `INFO`）
- `LOG_FILE`: 自定义日志文件路径（为空则使用默认文件）
- `LOG_MAX_BYTES`: 单个日志文件大小上限（默认 5MB）
- `LOG_BACKUP_COUNT`: 轮转备份文件数（默认 5）
