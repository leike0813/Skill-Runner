## ADDED Requirements

### Requirement: Run 观测详情页 MUST 使用稳定分区布局
系统 MUST 在内建管理界面的 Run 详情页使用稳定分区布局，确保文件浏览区、主对话区、错误区在长内容场景下仍可持续操作。

#### Scenario: 分区布局可持续操作
- **WHEN** 用户访问 `/ui/runs/{request_id}`
- **THEN** 页面同时提供文件浏览区、stdout 主对话区、stderr 独立区
- **AND** 用户无需切换页面即可完成查看输出与提交 reply

#### Scenario: 长内容不拉伸整页
- **WHEN** 文件树、文件预览或日志内容持续增长
- **THEN** 对应分区在内部容器滚动
- **AND** 页面主结构保持稳定，不出现无限增高导致的交互退化
