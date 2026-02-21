## Context

当前 skill 包校验集中在 `SkillPackageValidator` 的代码分支中，规则分散在多个 if/raise 逻辑里。  
这使得以下问题长期存在：
- 规则可见性弱，前后端与文档难以共享同一合同源；
- 安装与临时上传虽复用同一类，但缺少“独立合同文件”作为演进基线；
- `runner.json.engines` 被强制必填，无法表达“默认全支持 + 局部禁用”的真实需求。

同时，run 创建阶段尚未形成以 `effective_engines` 为准的强约束，前端难以获得稳定可枚举选项。

## Goals / Non-Goals

**Goals:**
- 将 skill package/runner manifest 的结构合同抽离为独立 schema 文件并接入校验流程。
- 为 `input/parameter/output` schema 增加服务端 meta-schema 约束，避免弱约定导致运行期才暴露错误。
- 将 engine 声明从“仅 allow-list”升级为“allow-list 可选 + deny-list 过滤”模型。
- 在安装、临时上传、run 创建、管理 API 四条路径上统一 `effective_engines` 语义。
- 输出可测试、可观测的错误行为（稳定错误码与验证失败信息）。

**Non-Goals:**
- 不改变引擎执行器本身（codex/gemini/iflow）行为。
- 不在本 change 引入新的引擎类型。
- 不重写所有历史 schema 文件，仅新增并接入本次所需合同文件。

## Decisions

### Decision 1: 新增独立 runner/skill package schema，并由校验器加载
在 `server/assets/schemas/` 下新增 manifest 合同 schema（含 `engines`、`unsupported_engines`、`execution_modes`、`schemas`、`artifacts` 等字段规则），由 `SkillPackageValidator` 统一加载执行。

Rationale:
- 规则“外置化”后更利于审查与版本演进。
- 安装与临时上传可天然复用同一份合同定义，降低漂移风险。

Alternative considered:
- 继续保留纯硬编码校验，仅增加注释文档。  
Rejected: 无法消除规则分散问题，且难以保证多入口行为一致。

### Decision 1.1: 增加 input/parameter/output meta-schema 预检
新增三份 schema 合同：
- `skill_input_schema.schema.json`
- `skill_parameter_schema.schema.json`
- `skill_output_schema.schema.json`

上传校验时在“文件存在”之后执行“内容结构预检”。  
其中仅对 Runner 会消费的扩展键做约束（如 `x-input-source`、`x-type`），其余 JSON Schema 标准字段保持宽松兼容。

Rationale:
- 将“文档约定”升级为“服务端可执行约束”。
- 提前发现 schema 书写错误，避免 run 阶段失败。

Alternative considered:
- 继续仅在运行时用业务 payload 去触发 schema 错误。  
Rejected: 错误反馈滞后且定位成本高。

### Decision 2: 引入统一的 engine policy 解析函数
新增统一解析逻辑（可位于 validator 或 manifest service）：
- `declared_engines = engines if provided else ALL_SUPPORTED_ENGINES`
- `effective_engines = declared_engines - unsupported_engines`
- 校验 `engines ∩ unsupported_engines = ∅`
- 校验 `effective_engines` 非空

并将结果写入运行时 manifest/DTO，供 jobs 与 management API 直接消费。

Rationale:
- 避免每个入口自行推导有效引擎，消除重复逻辑。
- 前端与后端都可读取同一“最终可执行集合”。

Alternative considered:
- 仅在 UI 层做默认推导。  
Rejected: 服务端仍缺少强约束，无法阻止非法执行请求。

### Decision 3: run 创建阶段新增 engine gating
在 `POST /v1/jobs`（及临时 run 创建路径）对请求引擎执行强校验：
- 若请求引擎不在 `effective_engines`，返回 `400`；
- 错误码固定为 `SKILL_ENGINE_UNSUPPORTED`；
- 保留原有 `execution_mode` 校验，与 engine 校验并列执行。

Rationale:
- 将“可执行引擎”从软约束升级为硬约束，避免运行期才发现不支持。

Alternative considered:
- 仅记录 warning 并尝试继续执行。  
Rejected: 失败路径不可预测，影响错误定位与客户端体验。

### Decision 4: 管理 API 明确返回有效引擎字段
管理侧 skill 响应新增或稳定化以下字段：
- `effective_engines`（供前端枚举）
- `engines`（原始声明，可空）
- `unsupported_engines`（原始声明，可空）

Rationale:
- 前端无需推导默认值或做额外策略判断。
- 便于调试“声明值”与“计算值”的差异。

## Risks / Trade-offs

- [历史 skill 兼容风险] 旧包若依赖“engines 必填”假设，迁移后需要重新理解默认语义  
  → Mitigation: 在文档中明确“缺失 engines = 全量支持”，并补充单测覆盖。

- [合同与实现偏移风险] schema 更新后实现未同步  
  → Mitigation: 为 schema 关键约束添加 validator 单测，CI 中校验安装/临时上传共同行为。

- [错误码扩展风险] 客户端尚未处理 `SKILL_ENGINE_UNSUPPORTED`  
  → Mitigation: 在 API 文档与 e2e client 中同步更新错误处理。

## Migration Plan

1. 新增并提交 manifest schema 文件与加载器。
2. 新增 input/parameter/output meta-schema 文件。
3. 重构 `SkillPackageValidator`，保留 zip/path/id/version 等结构校验，同时接入 schema 驱动字段校验。
4. 接入 engine policy 统一解析，并在 manifest DTO 中暴露 `effective_engines`。
5. 在 jobs 创建入口新增 engine gating（含错误码）。
6. 更新 management API 输出字段与文档。
7. 补充单测并执行全量单元测试回归。

Rollback:
- 如需回滚，可恢复到旧 validator 分支逻辑并忽略新字段，但需同时回滚文档与 API 错误码变更。

## Open Questions

- `SKILL_ENGINE_UNSUPPORTED` 的错误响应体是否需要额外包含 `effective_engines` 以便客户端直接提示可选值。
- `ALL_SUPPORTED_ENGINES` 的来源是否固定为静态枚举，还是读取当前运行时可用引擎集合（本 change 默认采用静态支持枚举）。
