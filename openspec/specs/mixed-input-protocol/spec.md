# mixed-input-protocol Specification

## Purpose
TBD - created by archiving change inline-input-mixed-payload. Update Purpose after archive.
## Requirements
### Requirement: `input` MUST support inline payload via request body
系统 MUST 支持客户端在 `POST /v1/jobs` 请求体中直接提供 `input` JSON。

#### Scenario: inline input create request
- **WHEN** skill 的 input 字段被声明为 inline 来源
- **AND** 客户端在请求体中提供对应 `input.<key>`
- **THEN** 系统接受并保存该值用于后续执行

### Requirement: input source MUST support explicit source declaration
`input.schema.json` 字段 MUST 支持 `x-input-source` 扩展，允许值为 `file` 或 `inline`。
若未声明，MUST 默认按 `file` 处理以保证兼容。

#### Scenario: default to file source
- **WHEN** input 字段未设置 `x-input-source`
- **THEN** 系统按文件输入处理并从 `uploads/` 解析

### Requirement: inline and file inputs MUST be validated separately
系统 MUST 按来源拆分 input 校验逻辑。

#### Scenario: inline required missing on create
- **WHEN** inline required 字段在请求体 `input` 中缺失
- **THEN** `POST /v1/jobs` 返回 400

#### Scenario: file required missing before upload
- **WHEN** file required 字段对应上传文件缺失
- **THEN** 请求不能成功执行，并返回 input 校验失败

### Requirement: input context MUST preserve mixed value types
运行时注入的 `input` 上下文 MUST 支持混合类型：
- 文件输入为路径字符串
- inline 输入为原始 JSON 值

#### Scenario: mixed context render
- **WHEN** 一个 skill 同时定义 file 与 inline 输入
- **THEN** prompt 渲染上下文中的 `input` 同时包含路径和值

### Requirement: cache key MUST include inline input hash
缓存键 MUST 纳入 inline input 的稳定哈希。

#### Scenario: cache key differs by inline payload
- **WHEN** 文件输入和 parameter 相同但 inline input 不同
- **THEN** 两次请求缓存键不同，不应误命中

