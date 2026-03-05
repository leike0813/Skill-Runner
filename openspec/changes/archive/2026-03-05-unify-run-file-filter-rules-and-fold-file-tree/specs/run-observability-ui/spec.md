## ADDED Requirements

### Requirement: 管理 UI Run 文件树 MUST 默认目录折叠

管理 UI run 详情页文件树 MUST 在初始渲染时将所有目录设为折叠状态，并允许用户按目录逐级展开。

#### Scenario: run detail tree starts collapsed
- **WHEN** 用户首次打开 `/ui/runs/{request_id}`
- **THEN** 文件树中的目录节点默认处于折叠状态
- **AND** 文件节点在目录展开前不可见

#### Scenario: directory node toggles expand/collapse
- **WHEN** 用户点击目录节点
- **THEN** 该目录在折叠与展开状态间切换
- **AND** 不影响文件预览接口行为

### Requirement: 管理 UI run 文件浏览 MUST obey explorer denylist filtering

管理 UI 展示的 run 文件树与预览 MUST 服从 run explorer 过滤规则（复用 debug 黑名单），并完全隐藏命中过滤项。

#### Scenario: ignored directories are absent from tree
- **WHEN** run 目录包含命中黑名单的目录（例如 `node_modules`）
- **THEN** 文件树中 MUST 不显示这些目录节点
- **AND** 其子文件也 MUST 不显示
