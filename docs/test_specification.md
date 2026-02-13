# 测试规范文档 (Test Specification)

本文档约定了本项目中不同类型测试与脚本执行的标准环境和操作流程。

## 1. 环境定义

项目主要涉及两类运行环境：

1.  **Conda 环境 (`DataProcessing`)**:
    -   **用途**: 用于运行通用的 Python 维护脚本、在开发过程中执行单元测试，以及作为 IDE 的默认解释器环境。
    -   **依赖**: 包含项目运行所需的基础 Python 包 (如 `jsonschema`, `tomlkit`, `fastapi` 等)。
    -   **激活方式**: `conda activate DataProcessing`

2.  **UV 隔离环境 (`.venv` via `tests/integration/run_integration_tests.sh`)**:
    -   **用途**: 专门用于 **Skill 集成测试**。
    -   **特点**: 由 `tests/integration/run_integration_tests.sh` 脚本自动通过 `uv` 管理，确保测试在纯净、隔离且与生产环境一致的依赖环境中运行。

## 2. 操作规范

### 2.1 通用脚本与单元测试 (Unit Tests & Scripts)

所有非集成测试的脚本执行，**必须** 在 `DataProcessing` Conda 环境下进行。

**适用场景**:
- 运行 `python scripts/some_utility.py`
- 运行 `pytest tests/unit/`
- 运行 `python server/main.py` (开发调试模式)

**执行命令**:
```bash
# 1. 确保已通过 Conda 激活环境
conda activate DataProcessing

# 2. 执行命令
python scripts/my_script.py
pytest tests/unit/
```

### 2.2 Skill 集成测试 (Integration Tests)

所有针对 Skill 的端到端集成测试，**必须** 使用 `tests/integration/run_integration_tests.sh` 脚本执行。

**严禁** 直接使用 python 运行 `tests/integration/run_integration_tests.py`，因为这会跳过必要的环境变量注入（如 `SKILL_RUNNER_DATA_DIR`）和环境隔离。

**适用场景**:
- 验证某个 Skill (如 `demo-bible-verse`) 在特定引擎 (Gemini/Codex) 下的完整执行流程。
- 回归测试。

**执行命令**:
```bash
# 格式: ./tests/integration/run_integration_tests.sh [args passed to run_integration_tests.py]

# 示例 1: 测试 demo-bible-verse 技能，使用 Gemini 引擎 (详细日志)
./tests/integration/run_integration_tests.sh -k demo-bible-verse -e gemini -v

# 示例 2: 测试所有 Pandas 相关技能，使用 Codex 引擎
./tests/integration/run_integration_tests.sh -k pandas -e codex

# 示例 3: 运行所有集成测试
./tests/integration/run_integration_tests.sh
```

**Suite 扩展字段**:
- `skill_source`: `installed`（默认）或 `temp`
- `skill_fixture`: 当 `skill_source=temp` 时，从 `tests/fixtures/skills/<skill_fixture>/` 读取并打包临时上传

**说明**:
- `installed`：沿用现有内部编排流程（不经过 HTTP 路由）。
- `temp`：通过内部服务调用临时 skill 执行链路（`TempSkillRunManager` + `create_run_for_skill`）。

### 2.3 Skill 包安装接口集成测试

针对 `POST /v1/skill-packages/install` 与 `GET /v1/skill-packages/{request_id}` 的接口集成测试，使用 pytest 在进程内执行完整 API 流程。

**覆盖范围**:
- 新技能安装成功并可被 `/v1/skills/{skill_id}` 发现
- 升版更新时旧版本归档 (`skills/.archive/{skill_id}/{old_version}`)
- 降级更新被拒绝
- 非法技能包（缺少必需文件）被拒绝

**执行命令**:
```bash
conda run --no-capture-output -n DataProcessing python -u -m pytest tests/integration/test_skill_package_install_api.py -q
```

### 2.4 临时 Skill 运行接口集成测试

针对 `/v1/temp-skill-runs` 两步式流程的集成测试，使用 pytest + TestClient 在进程内执行。

**覆盖范围**:
- 创建临时请求 -> 上传临时 skill 包 -> 启动执行
- 状态/结果接口与 jobs 语义对齐
- 临时 skill 不进入持久 `skills/` 注册表
- 终态后临时 skill 包与解压目录清理
- 非法临时 skill 包上传返回 400

**执行命令**:
```bash
conda run --no-capture-output -n DataProcessing python -u -m pytest tests/integration/test_temp_skill_runs_api.py -q
```

### 2.5 REST E2E Tests

REST 级别 E2E 测试使用 FastAPI TestClient 在进程内执行完整 API 流程。
覆盖：create job、upload、status、result、artifacts、bundle。

**执行命令**:
```bash
./tests/e2e/run_e2e_tests.sh -k demo-bible-verse -e gemini -vv
```

**规则**:
- 若 `engine` 不在 skill 的 `engines` 列表中，测试应预期失败（以 `workspace_manager` 抛错为判定）。
- E2E 与集成测试共用 `tests/suites/*.yaml` 输入格式。
- 当 suite 配置 `skill_source=temp` 时，E2E 走 `/v1/temp-skill-runs` 两步接口。

### 2.5 日志配置 (Logging)

测试与脚本支持通过环境变量配置日志输出，默认写入 `data/logs/`。

**常用变量**:
- `LOG_LEVEL`: 日志级别（默认 `INFO`）。
- `LOG_FILE`: 自定义日志文件路径（为空则使用默认文件）。
- `LOG_MAX_BYTES`: 单个日志文件大小上限（默认 5MB）。
- `LOG_BACKUP_COUNT`: 轮转备份文件数（默认 5）。

**示例**:
```bash
LOG_LEVEL=DEBUG LOG_FILE=/tmp/skill_runner.log LOG_MAX_BYTES=1048576 LOG_BACKUP_COUNT=3 \
./tests/integration/run_integration_tests.sh -k demo-bible-verse -e gemini -v
```

## 3. 常见问题 (FAQ)

**Q: 为什么集成测试不能用 Conda 环境？**
A: 集成测试旨在模拟真实的生产运行环境。`tests/integration/run_integration_tests.sh` 使用 `uv` 创建的虚拟环境更接近 Docker 容器或生产服务器的部署状态，能有效避免 Conda 环境中可能存在的环境污染问题。同时，`tests/integration/run_integration_tests.sh` 负责设置关键的 `DATA_DIR` 等环境变量，直接运行 Python 脚本可能会导致产生脏数据或路径错误。

**Q: 我开发了一个新功能，如何验证？**
1.  首先在 Conda 环境下编写并运行 **单元测试** (`pytest tests/unit/`)，无需启动完整服务。
2.  单元测试通过后，使用 `./tests/integration/run_integration_tests.sh` 运行相关的 **集成测试**，验证端到端逻辑。
