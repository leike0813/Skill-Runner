# ui-skill-browser Specification

## Purpose
TBD - created by archiving change ui-skill-browser-and-auth-hardening. Update Purpose after archive.
## Requirements
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

### Requirement: Skill 浏览与管理信息 MUST 通过通用管理 API 暴露
系统 MUST 提供可复用的 Skill 管理接口，以支持内置 UI 与外部前端复用同一数据语义。

#### Scenario: 获取 Skill 列表
- **WHEN** 客户端请求 Skill 列表
- **THEN** 响应包含技能标识、版本、引擎支持、健康状态等稳定字段

#### Scenario: 获取 Skill 详情与结构化内容
- **WHEN** 客户端请求 Skill 详情
- **THEN** 响应包含 schemas/entrypoints/files 等结构化信息
- **AND** 文件路径越界或不存在时返回标准错误码

### Requirement: Skill 管理页面字段 MUST 对齐 management API
系统 MUST 保证内建 Skill 管理页面列表与详情均基于 management API 稳定字段。

#### Scenario: Skill 列表渲染
- **WHEN** 页面渲染 Skill 列表
- **THEN** 技能标识、版本、引擎支持、健康状态来源于 management API

#### Scenario: Skill 详情渲染
- **WHEN** 页面渲染 Skill 详情与文件浏览
- **THEN** 页面使用 management API 结构化字段
- **AND** 不依赖旧 UI 专用数据接口

