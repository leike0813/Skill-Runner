# 项目结构说明 (Project Structure)

本文档详细说明 Skill Runner 项目的目录结构及其用途。

## 根目录结构

```
Skill-Runner/
├── data/                   # 运行时数据存储
├── docs/                   # 项目文档
├── references/             # 参考资料与外部文档
├── server/                 # 服务端核心代码
├── skills/                 # 技能注册表 (Skill Registry)
├── tests/                  # 测试套件
├── tests/engine_integration/run_engine_integration_tests.py # 引擎集成测试入口脚本
├── tests/e2e/run_e2e_tests.py # REST E2E 测试入口脚本
├── data/runs.db            # 运行元数据/缓存索引 (sqlite)
├── pyproject.toml          # Python 项目配置与依赖
└── uv.lock                 # 依赖锁定文件
```

## 核心代码目录 (`server/`)

服务端逻辑的核心区域，采用 FastAPI 架构。

```
server/
├── adapters/               # 执行引擎适配器
│   ├── base.py             # 适配器基类 (EngineAdapter)
│   ├── gemini_adapter.py   # Gemini CLI 适配器
│   ├── codex_adapter.py    # Codex CLI 适配器
│   └── iflow_adapter.py    # iFlow CLI 适配器
├── assets/                 # 静态资源与配置模板
│   ├── configs/            # 强制配置文件 (Enforced Configs)
│   ├── schemas/            # JSON Schemas (Settings/Profile)
│   └── templates/          # Jinja2 Prompt 模板
├── routers/                # API 路由定义
│   ├── jobs.py             # 任务运行相关接口
│   └── skills.py           # 技能管理相关接口
├── services/               # 业务逻辑服务
│   ├── job_orchestrator.py # 任务编排与调度
│   ├── skill_registry.py   # 技能扫描与注册
│   ├── workspace_manager.py# 运行目录与文件管理
│   ├── config_generator.py # 配置生成工具
│   └── schema_validator.py # 数据校验服务
├── config.py               # 全局配置对象 (Singleton)
├── core_config.py          # 默认配置定义 (YACS)
├── main.py                 # FastAPI 应用入口
└── models.py               # Pydantic 数据模型定义
```

## 技能目录 (`skills/`)

存放所有注册的技能，每个子目录代表一个独立的技能。

```
skills/
└── [skill_id]/             # 技能唯一标识
    ├── assets/             # 技能特定资源
    │   ├── runner.json     # 技能清单文件 (Manifest)
    │   ├── service.py/sh   # 技能入口脚本
    │   └── *.json          # 引擎特定默认配置 (如 codex_config.toml)
    ├── SKILL.md            # 技能说明文档
    └── ...                 # 其他辅助文件
```

## 测试目录 (`tests/`)

包含单元测试和集成测试框架。

```
tests/
├── engine_integration/     # 引擎执行链路集成测试
│   ├── run_engine_integration_tests.py # 引擎集成测试运行器
│   ├── run_engine_integration_tests.sh # 引擎集成测试脚本封装
│   └── suites/             # 引擎集成测试套件定义 (YAML)
├── api_integration/        # API/UI 契约集成测试
│   ├── test_*.py
│   └── run_api_integration_tests.sh
├── e2e/                    # REST E2E 测试
│   ├── run_e2e_tests.py     # E2E 测试运行器
│   └── run_e2e_tests.sh     # E2E 脚本封装
├── fixtures/               # 测试用静态文件
├── unit/                   # 单元测试 (Pytest)
│   ├── test_adapters.py
│   ├── test_config.py
│   └── ...
└── verify_*.py             # 手动验证脚本 (Legacy)
```

## 运行时目录 (`data/`)

系统运行时自动生成的目录，通常不纳入版本控制。

```
data/
└── runs/                   # 执行记录
    └── [run_id]/           # 单次运行的工作区（内部）
        ├── uploads/        # 用户上传的文件
        ├── artifacts/      # 技能生成的产物
        ├── logs/           # 运行日志 (stdout/stderr/prompt)
        ├── result/         # 结构化结果
        ├── .gemini/        # Gemini 引擎工作区
        └── .codex/         # Codex 引擎工作区

data/
└── requests/               # 运行前请求暂存
    └── [request_id]/
        ├── uploads/        # 上传输入文件
        ├── request.json    # 请求原始参数
        └── input_manifest.json  # 输入文件哈希清单
```

## 关键文件说明

- **`pyproject.toml`**: 项目元数据、依赖列表和构建配置。
- **`tests/engine_integration/run_engine_integration_tests.py`**: 引擎链路集成测试入口，统一通过夹具执行测试套件。
- **`tests/e2e/run_e2e_tests.py`**: REST E2E 测试入口，覆盖 API 全流程。
- **`server/core_config.py`**: 定义了系统的核心配置项（如默认径、超时设置等），采用 YACS 配置库管理。
