# 通用测试框架设计方案 (Universal Test Framework Design)

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
├── integration/
│   └── run_integration_tests.py # 通用测试执行器 (Integration Runner)
├── fixtures/                 # 具体的测试文件资源 (图片, markdown, etc)
│   ├── basic_numbers.md
│   └── secure_image.jpg
└── suites/                   # 测试套件定义 (每个 Skill 一个 YAML/JSON)
    ├── demo-prime-number.yaml
    ├── demo-prime-number-csv-mismatch.yaml
    └── demo-bible-verse.yaml
```

## 3. 测试用例定义规范 (Test Case Schema)

采用 YAML 格式定义测试用例，清晰易读。

### 示例 (`tests/suites/demo-prime-number.yaml`)

```yaml
skill_id: "demo-prime-number"
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

## 4. 核心组件：Test Runner (`tests/integration/run_integration_tests.py`)

Runner 将是一个 Python 脚本，负责读取 YAML 并在本地**黑盒调用**我们的 Service 层 (或 API Client)。

### 执行流程

1.  **Load**: 读取 `tests/suites/*.yaml`。
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
    *   轮询检查 `status.json` 直到 `status` 为 `SUCCEEDED` 或 `FAILED`。
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
├── unit/                     # 单元测试
│   ├── test_schema_validator.py
│   ├── test_gemini_adapter.py
│   └── test_workspace_manager.py
├── integration/              # 上述的通用 Runner 和 Suites
│   ├── run_integration_tests.py
│   └── ...
```

### 关键测试点

1.  **SchemaValidator**:
    *   纯逻辑测试。验证 `validate_schema` 对各种合法/非法 JSON 的反应。
    *   验证 `files` vs `parameter` 的 schema 拆分逻辑。

2.  **GeminiAdapter** (Mocking):
    *   Mock `subprocess.create_subprocess_exec`。
    *   测试 Prompt 生成逻辑：
        *   验证 Strict Key-Matching 逻辑（文件存在 vs 不存在）。
        *   验证 Jinja2 模板渲染是否正确包含 `{{ input }}` 和 `{{ parameter }}`。

3.  **JobOrchestrator** (Mocking):
    *   Mock `SkillRegistry` 和 `WorkspaceManager`。
    *   验证 `strict validation` 失败时是否正确抛出异常。
    *   验证状态更新逻辑。

### 工具栈
- **Framework**: `pytest`
- **Mocking**: `unittest.mock` / `pytest-mock`
- **Coverage**: `pytest-cov` (可选)
