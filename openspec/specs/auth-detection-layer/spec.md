# auth-detection-layer Specification

## Purpose
TBD - created by archiving change introduce-auth-detection-layer. Update Purpose after archive.
## Requirements
### Requirement: Backend auth failures MUST be detected before generic user-input inference
系统 MUST 在 run 执行拿到引擎输出后、generic `waiting_user` 推断前执行 auth detection，并在高置信度命中时优先于 generic pending-interaction inference。

#### Scenario: 高置信度鉴权命中优先于等待态推断
- **WHEN** run 已完成引擎执行并拿到输出材料
- **AND** auth detection 命中高置信度 auth-required 规则
- **THEN** 系统必须在 generic `waiting_user` 推断前完成判定
- **AND** generic pending-interaction 推断必须被跳过

### Requirement: Auth detection MUST use a hybrid rule architecture
系统 MUST 采用“Python engine-specific detector + YAML rule pack”的混合模型。

#### Scenario: 结构化提取由 detector 完成
- **WHEN** 系统处理某引擎输出
- **THEN** 引擎专用结构化提取必须由 Python detector 实现

#### Scenario: 分类映射由规则包完成
- **WHEN** 系统完成证据提取
- **THEN** 文本/字段匹配和分类映射必须来自可校验的 YAML 规则包

### Requirement: Auth detection MUST produce structured internal results
任一 detector 命中 auth-like 模式时，系统 MUST 产出统一结构化结果。

#### Scenario: 统一结果字段
- **WHEN** 任一 rule 命中
- **THEN** detection 结果必须包含：
  - `classification`
  - `subcategory`
  - `confidence`
  - `engine`
  - `provider_id`
  - `matched_rule_ids`
  - `evidence_excerpt`
  - `evidence_sources`

### Requirement: Rule packs MUST be versioned and validated
系统 MUST 在启动时加载并校验 auth detection rule packs。

#### Scenario: 规则包非法 fail-fast
- **WHEN** rule pack 存在 duplicate rule id、非法 operator 或非法 subcategory
- **THEN** 系统启动必须失败
- **AND** 服务不得进入可运行状态

### Requirement: Detection MUST degrade conservatively for ambiguous auth-like failures
对于只呈现问题行为但缺乏稳定 auth 证据的样本，系统 MAY 产出 `auth_required` + `confidence=medium`，但 MUST 保持保守。

#### Scenario: medium 命中仅进入审计
- **WHEN** 输出只命中问题样本层
- **THEN** 系统可以产出 `auth_required`
- **AND** `confidence` 必须为 `medium`
- **AND** 编排层不得仅因该结果强制写 `failure_reason=AUTH_REQUIRED`

### Requirement: Detection results MUST be persisted to internal audit artifacts
每次 attempt 的 detection 结果 MUST 写入内部审计产物。

#### Scenario: Attempt meta 记录 auth detection
- **WHEN** detection 执行完成
- **THEN** `.audit/meta.{attempt}.json` 必须记录 `auth_detection`

#### Scenario: Parser diagnostics 记录 detection 命中
- **WHEN** detection 命中 `medium` 或 `high`
- **THEN** 系统必须写入对应 diagnostic entry
- **AND** 不修改 FCMP / 对外 runtime payload

