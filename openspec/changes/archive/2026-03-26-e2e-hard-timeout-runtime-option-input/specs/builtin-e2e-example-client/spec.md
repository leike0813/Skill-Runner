## ADDED Requirements

### Requirement: E2E Run Form MUST expose hard timeout runtime option with validated non-negative integer input

E2E 示例客户端的 Run Form MUST 始终显示 `hard_timeout_seconds` 输入控件，并在提交前校验其为非负整数。

#### Scenario: run form shows hard timeout spinbox
- **WHEN** 用户打开 installed skill 或 fixture skill 的 run form
- **THEN** 页面显示 `hard_timeout_seconds` 输入控件
- **AND** 该控件使用 number spinbox
- **AND** 设置 `min=0`
- **AND** 设置 `step=60`

#### Scenario: invalid hard timeout input is rejected
- **WHEN** 用户提交的 `hard_timeout_seconds` 为空、负数、非整数或包含小数
- **THEN** 客户端阻止提交
- **AND** 页面返回可读校验错误

#### Scenario: valid hard timeout is submitted explicitly
- **WHEN** 用户提交合法的 `hard_timeout_seconds`
- **THEN** 客户端在 create-run 请求中显式写入 `runtime_options.hard_timeout_seconds`
- **AND** 该值为整数

### Requirement: E2E Run Form MUST prefill hard timeout from skill default then service default

E2E 示例客户端 MUST 按稳定优先级预填 `hard_timeout_seconds`，优先 skill runtime default，缺失时回退服务级默认值。

#### Scenario: installed skill default wins
- **WHEN** installed skill detail 包含 `runtime.default_options.hard_timeout_seconds`
- **THEN** run form 预填该值

#### Scenario: fixture skill default wins
- **WHEN** fixture skill manifest 包含 `runtime.default_options.hard_timeout_seconds`
- **THEN** run form 预填该值

#### Scenario: service default fallback is used
- **WHEN** skill 未提供 `runtime.default_options.hard_timeout_seconds`
- **THEN** run form 使用 management runtime options 接口返回的服务默认值作为预填
