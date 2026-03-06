## ADDED Requirements

### Requirement: Platform cache fingerprint SHALL resolve engine defaults via adapter profile
`cache_key_builder` MUST 使用 adapter profile 的 `config_assets.skill_defaults_path`，并且 MUST NOT 再硬编码 engine 默认配置文件名。

#### Scenario: 计算技能指纹
- **WHEN** 平台为指定 engine 计算 skill fingerprint
- **THEN** 默认配置文件路径来自 adapter profile
- **AND** 平台层不包含 engine 文件名分支

### Requirement: Runtime adapter profile loader SHALL use unified engine catalog
Runtime adapter profile loader MUST read supported engines from a unified engine catalog source, and MUST NOT maintain a local hard-coded engine source-of-truth.

#### Scenario: 引擎列表更新
- **WHEN** 统一 engine catalog 增减 engine
- **THEN** profile loader 使用更新后的列表
- **AND** 无需同步修改本地硬编码引擎常量
