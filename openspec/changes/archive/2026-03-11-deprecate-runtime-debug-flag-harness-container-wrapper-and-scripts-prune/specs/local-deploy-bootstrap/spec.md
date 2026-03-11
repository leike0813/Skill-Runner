## MODIFIED Requirements

### Requirement: 系统 MUST 提供本地一键部署脚本
系统 MUST 保持 `scripts/` 目录只包含正式支持的部署、启动、发布或受支持运维脚本；历史兼容、排障和实验脚本 MUST 迁出主目录。

#### Scenario: supported scripts remain in scripts directory
- **WHEN** 用户查看项目根目录 `scripts/`
- **THEN** 其中仅包含当前正式支持的部署/启动/运维入口
- **AND** 历史兼容或一次性脚本不再与正式入口混放

#### Scenario: deprecated or forensic scripts are relocated
- **WHEN** 用户需要访问历史兼容或排障脚本
- **THEN** 可以分别在 `deprecated/scripts/` 或 `artifacts/scripts/` 找到
- **AND** README 与容器化文档不会再把它们列为正式入口
