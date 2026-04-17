# 通用测试框架设计方案 (Universal Test Framework Design)

> Note:
> 本文档保留了早期 YAML suite 驱动的测试框架设计背景。
> 当前 `tests/engine_integration/` 已迁移到 golden-driven pytest 体系；
> `tests/engine_integration/suites/` 现在仅保留给 E2E legacy case source 使用，
> `harness_fixture.py` 也不再是当前 engine integration 的实现入口。

## 1. 目标与背景

当前测试 (`verify_*.py`) 存在硬编码输入、验证逻辑耦合、不可复用等问题。本方案旨在设计一个**通用、数据驱动**的测试框架，实现以下目标：

1.  **解耦 (Decoupling)**: 测例定义 (数据) 与执行逻辑 (代码) 分离。
2.  **拟真 (Realistic)**: 模拟真实用户的 API 调用流程 (Create -> Upload -> Run -> Poll)。
3.  **可扩展 (Extensible)**: 支持为任意 Skill 添加测试用例，只需增加配置文件。
4.  **标准化验证 (Standardized Assertions)**: 提供统一的断言机制验证状态、产物和 JSON 输出。

## 2. 目录结构设计

建议将测试资源集中管理：

```text
tests/
├── engine_integration/
│   ├── harness_fixture.py
│   └── run_engine_integration_tests.py # 通用测试执行器 (Engine Integration Runner)
├── fixtures/                 # 具体的测试文件资源 (图片, markdown, etc)
│   ├── basic_numbers.md
│   └── secure_image.jpg
└── engine_integration/suites/ # 测试套件定义 (每个 Skill 一个 YAML/JSON)
    ├── demo-prime-number.yaml
    ├── demo-prime-number-csv-mismatch.yaml
    └── demo-bible-verse.yaml
```

## 3. 测试用例定义规范 (Test Case Schema)

采用 YAML 格式定义测试用例，清晰易读。

### 示例 (`tests/engine_integration/suites/demo-prime-number.yaml`)

```yaml
skill_id: "demo-prime-number"
skill_source: "temp"          # 可选: installed|temp，默认 installed
skill_fixture: "demo-prime-number"  # skill_source=temp 时使用
cases:
  - name: "Basic Primality Test"
    description: "Verify standard prime number filtering works"
    
    # 1. Parameter Payload (模拟 API Create Run)
    parameters:
      divisor: 1
    
    # 2. Input Files (模拟 API Upload)
    # 映射关系: Schema Key -> Fixture File Path (relative to tests/fixtures/)
    inputs:
      input_file: "basic_numbers.md"
    
    # 3. Expectations (断言)
    expectations:
      status: "succeeded"
      
      # 验证产物是否存在
      artifacts_present:
        - "primes.md"
      
      # 验证结果 JSON (支持简单的键值匹配)
      output_json:
        status: "success"
        # 它可以是具体的值，也可以是一些特殊标记 (设计中考虑)
        # 目前简单起见，仅支持值相等或 Key 存在检查
```

字段说明：
- `skill_source=installed`: 使用注册器解析后的已安装 skill（来源可能是 `skills_builtin/` 或用户目录 `skills/`，同 ID 用户优先）。
- `skill_source=temp`: 从 `tests/fixtures/skills/<skill_fixture>/` 打包后走临时 skill 执行路径。

## 4. 核心组件：Test Runner (`tests/engine_integration/run_engine_integration_tests.py`)

Runner 将是一个 Python 脚本，负责读取 YAML 并在本地**黑盒调用**我们的 Service 层 (或 API Client)。

### 执行流程

1.  **Load**: 读取 `tests/engine_integration/suites/*.yaml`。
2.  **Setup**:
    *   生成 request_id 并写入 request.json。
3.  **Upload**:
    *   如果定义了 `inputs`：
        *   从 `tests/fixtures/` 读取指定文件。
        *   内存中构建 ZIP 包（模拟前端行为）。
        *   调用 `WorkspaceManager.handle_upload(request_id, zip_bytes)`。
4.  **Execute**:
    *   调用 `WorkspaceManager.create_run(...)` 后再触发 `JobOrchestrator.run_job(...)`。
    *   若 `engine` 不在 `skill.engines` 内，应在 `create_run` 阶段抛错并视为预期失败。
5.  **Poll/Wait**:
    *   轮询检查 `.state/state.json` 直到 `status` 为 `SUCCEEDED` 或 `FAILED`。
6.  **Verify**:
    *   **Status Check**: 实际状态 == expect.status?
    *   **Artifacts Check**: `data/runs/<id>/artifacts/` 下是否存在指定文件?
    *   **Result Check**: 读取 `result/result.json`，验证 `expectations.output_json` 中的键值对是否匹配。

## 5. 优势

- **无需写代码**: 添加新测试只需添加 YAML 和 Fixture 文件。
- **环境隔离**: 每个 TestCase 都是一个新的 Run UUID。
- **覆盖全链路**: 完整覆盖了参数解析、Zip解压、文件映射匹配、Prompt生成、CLI执行、结果解析全过程。

## 6. 单元测试策略 (Unit Testing Strategy)

除了上述的集成测试 Runner，我们需要一套基于 `pytest` 的单元测试来验证核心组件的原子逻辑。

### 目录规划
```text
tests/
├── unit/                     # 单元测试（160+ test files）
│   ├── test_schema_validator.py        # Platform: Schema 校验
│   ├── test_gemini_adapter.py          # Engines: Gemini 适配器
│   ├── test_codex_adapter.py           # Engines: Codex 适配器
│   ├── test_iflow_adapter.py           # Engines: iFlow 适配器
│   ├── test_opencode_adapter.py        # Engines: OpenCode 适配器
│   ├── test_job_orchestrator.py        # Orchestration: 作业编排
│   ├── test_run_store.py               # Orchestration: Run 存储
│   ├── test_runtime_event_protocol.py  # Protocol: FCMP 事件协议
│   ├── test_run_observability.py       # Observability: 可观测性
│   ├── test_session_invariant_contract.py  # Contract: 状态机不变量
│   ├── test_session_state_model_properties.py  # Contract: 状态模型属性
│   ├── test_fcmp_mapping_properties.py     # Contract: FCMP 映射
│   ├── test_protocol_state_alignment.py    # Contract: 协议状态对齐
│   ├── test_skill_registry.py          # Skill: 注册表
│   ├── test_skill_patcher.py           # Skill: 运行时补丁
│   ├── test_workspace_manager.py       # Orchestration: 工作区
│   └── ...                             # (更多测试文件)
├── common/                   # 共享测试合同与工具
│   ├── session_invariant_contract.py   # 状态机不变量合同
│   └── skill_fixture_loader.py         # Skill fixture 加载器
├── engine_integration/       # 引擎执行链路集成测试
│   ├── run_engine_integration_tests.py
│   └── suites/*.yaml
├── api_integration/          # API/UI 契约集成测试
│   └── test_*.py
├── e2e/                      # 端到端测试
│   ├── run_e2e_tests.py
│   ├── run_local_e2e_tests.py
│   └── run_container_e2e_tests.py
├── fixtures/                 # 测试数据
│   └── skills/               # Skill fixture 包
│       ├── demo-prime-number/
│       ├── demo-bible-verse/
│       ├── demo-auto-skill/
│       ├── demo-interactive-skill/
│       └── ...
├── assets/                   # 测试资源文件
└── config/                   # 测试配置
```

### 关键测试点

单元测试已按组件分类全面覆盖：

1.  **Contract Tests（合同测试）**:
    *   `test_session_invariant_contract.py` — 状态机不变量守护
    *   `test_session_state_model_properties.py` — 状态模型属性测试
    *   `test_fcmp_mapping_properties.py` — FCMP 映射属性
    *   `test_protocol_state_alignment.py` — 协议状态对齐

2.  **Adapter Tests（适配器测试）**:
    *   每个引擎独立测试（`test_codex_adapter.py`、`test_gemini_adapter.py`、`test_iflow_adapter.py`、`test_opencode_adapter.py`）
    *   共享组件测试（`test_adapter_command_profiles.py`、`test_adapter_parsing.py` 等）

3.  **Orchestration Tests（编排测试）**:
    *   `test_job_orchestrator.py` — 作业编排逻辑
    *   `test_run_store.py` — Run 持久化
    *   `test_workspace_manager.py` — 工作区管理

4.  **Auth Tests（鉴权测试）**:
    *   每个引擎 OAuth 流程测试
    *   `test_auth_driver_registry.py` — 鉴权驱动注册
    *   `test_engine_auth_flow_manager.py` — 鉴权流程管理

5.  **Architecture Guard Tests（架构守护测试）**:
    *   `test_runtime_core_import_boundaries.py` — 导入边界检查
    *   `test_runtime_no_orchestration_imports.py` — Runtime 不依赖 Orchestration
    *   `test_services_topology_rules.py` — 服务拓扑规则
    *   `test_runtime_auth_no_engine_coupling.py` — Auth Runtime 不耦合引擎

### 工具栈
- **Framework**: `pytest`
- **Mocking**: `unittest.mock` / `pytest-mock`
- **Coverage**: `pytest-cov` (可选)
