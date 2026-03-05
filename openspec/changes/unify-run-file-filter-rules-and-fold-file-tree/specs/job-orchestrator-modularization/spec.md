## ADDED Requirements

### Requirement: Run bundle candidate filtering MUST be rule-file driven

系统 MUST 使用独立规则文件管理 run bundle 的候选文件过滤，而不是在代码中硬编码散落规则。

#### Scenario: non-debug bundle uses allowlist file
- **WHEN** orchestration 构建 `debug=false` 的 run bundle
- **THEN** 系统 MUST 使用非 debug 白名单规则文件筛选候选文件
- **AND** 首版白名单行为 MUST 与当前语义等价（`result/result.json` 与 `artifacts/**`）

#### Scenario: debug bundle uses denylist file
- **WHEN** orchestration 构建 `debug=true` 的 run bundle
- **THEN** 系统 MUST 使用 debug 黑名单规则文件排除候选文件
- **AND** 命中任意层级 `node_modules` 的目录与文件 MUST 被排除

### Requirement: Run explorer filtering MUST reuse debug denylist contract

run 文件树和文件预览 MUST 复用 debug 黑名单规则文件，保持“打包可见集合”与“浏览可见集合”一致。

#### Scenario: filtered paths are hidden from run explorer
- **WHEN** 客户端读取 run 文件树
- **THEN** 命中 debug 黑名单规则的目录与文件 MUST NOT 出现在 entries 中

#### Scenario: filtered file preview is rejected
- **WHEN** 客户端请求 run 文件预览且路径命中 debug 黑名单规则
- **THEN** 系统 MUST 拒绝该预览请求
- **AND** MUST NOT 通过手工路径输入绕过过滤
