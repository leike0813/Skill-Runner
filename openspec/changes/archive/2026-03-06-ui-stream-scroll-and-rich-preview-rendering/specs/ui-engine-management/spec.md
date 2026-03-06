## MODIFIED Requirements

### Requirement: 管理 UI Run Detail MUST 提供协议流双视图
系统 MUST 在管理 UI Run Detail 协议流面板中，避免刷新时强制抢占用户滚动位置，并支持摘要到详情的逐条展开查看。

#### Scenario: 用户上翻后刷新不强制拉底
- **WHEN** 用户在某协议流面板手动滚动到非底部位置
- **AND** 系统刷新该面板数据
- **THEN** 面板滚动位置保持用户当前位置

#### Scenario: 用户贴底时刷新继续跟随
- **WHEN** 用户处于某协议流面板底部附近
- **AND** 新事件到达并刷新面板
- **THEN** 面板自动跟随到底部显示最新内容

#### Scenario: 摘要气泡展开详情
- **WHEN** 用户点击摘要气泡
- **THEN** 面板展开该条详情并显示关键字段与结构化内容
- **AND** 同一面板其余展开项自动折叠

### Requirement: 管理 UI 文件预览 MUST 支持格式化渲染
系统 MUST 在 Skill Browser 与 Run Observation 文件预览区域提供高对比可读样式，并支持常见文本格式高亮渲染。

#### Scenario: Skill Browser 长文件预览
- **WHEN** 文件内容超过预览容器高度
- **THEN** 预览区域保持固定高度并提供纵向滚动

#### Scenario: 常见格式高亮渲染
- **WHEN** 预览文件格式为 `json|yaml|toml|python|javascript`
- **THEN** 预览渲染为可读高亮视图
- **AND** 渲染失败时回退普通文本显示

## ADDED Requirements

### Requirement: 文件树与预览交互 MUST 使用统一复用模块
系统 MUST 在管理 Run Observation、Skill Browser 与 E2E Run 页面复用同一文件树/预览交互模块，避免页面间行为漂移。

#### Scenario: 三处页面目录折叠行为一致
- **WHEN** 用户打开文件树
- **THEN** 目录默认折叠
- **AND** 展开/收起行为在三处页面一致

### Requirement: Run Observation 布局 MUST 保持稳定可读
系统 MUST 固定三流窗口高度，并将 Raw stderr 区域改为折叠式全宽区域，避免布局随内容抖动。

#### Scenario: 三流高度不随模式变化
- **WHEN** 用户在摘要视图与 raw 视图之间切换
- **THEN** FCMP/RASP/Orchestrator 三流窗口高度保持一致

#### Scenario: 折叠 stderr 红点提示
- **WHEN** Raw stderr 处于折叠状态且存在输出
- **THEN** 折叠栏显示未读红点提示
