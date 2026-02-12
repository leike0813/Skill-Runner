## ADDED Requirements

### Requirement: 系统 MUST 提供单个 skill 的包结构浏览页面（只读）
系统 MUST 提供 `/ui/skills/{skill_id}` 页面，用于浏览该 skill 包结构与元信息。

#### Scenario: 打开 skill 详情页
- **WHEN** 用户访问 `/ui/skills/{skill_id}`
- **THEN** 页面显示该 skill 的基本信息
- **AND** 页面显示 skill 包目录结构

### Requirement: 系统 MUST 支持 skill 文件只读预览
系统 MUST 提供文件预览接口，允许用户在 UI 中查看文本文件内容，不允许修改。

#### Scenario: 文本文件预览
- **WHEN** 用户查看 skill 内文本文件
- **THEN** 系统返回文件内容预览
- **AND** 页面不提供编辑或写入能力

### Requirement: 系统 MUST 对二进制文件和超大文件进行安全降级
系统 MUST 对不可安全预览的文件返回降级提示，不返回原始内容。

#### Scenario: 二进制文件预览
- **WHEN** 用户查看二进制文件
- **THEN** 页面显示“不可预览”
- **AND** 元信息显示“无信息”

#### Scenario: 超大文本文件预览
- **WHEN** 文件大小超过 256KB
- **THEN** 页面显示“文件过大不可预览”

### Requirement: 文件浏览 MUST 严格受限于目标 skill 根目录
系统 MUST 防止任意路径访问与目录逃逸。

#### Scenario: 路径穿越
- **WHEN** 请求包含 `..` 或绝对路径
- **THEN** 系统拒绝请求（4xx）

#### Scenario: skill 外路径访问
- **WHEN** 解析后的目标路径不在 `skills/{skill_id}` 内
- **THEN** 系统拒绝请求（4xx）
