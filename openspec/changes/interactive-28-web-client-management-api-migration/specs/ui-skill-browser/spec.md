## ADDED Requirements

### Requirement: Skill 管理页面字段 MUST 对齐 management API
系统 MUST 保证内建 Skill 管理页面列表与详情均基于 management API 稳定字段。

#### Scenario: Skill 列表渲染
- **WHEN** 页面渲染 Skill 列表
- **THEN** 技能标识、版本、引擎支持、健康状态来源于 management API

#### Scenario: Skill 详情渲染
- **WHEN** 页面渲染 Skill 详情与文件浏览
- **THEN** 页面使用 management API 结构化字段
- **AND** 不依赖旧 UI 专用数据接口
