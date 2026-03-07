## MODIFIED Requirements

### Requirement: 示例客户端 MUST 提供结果解包与可视化展示
示例客户端 MUST 在 Observation 页面内展示终态结果摘要与文件树预览能力，不再依赖独立 Result 页面。  
文件树预览数据 MUST 来自后端 jobs 文件接口返回的 canonical 预览载荷，客户端 MUST NOT 本地解压 bundle 并自行构建预览内容。

#### Scenario: Observation 终态结果与产物展示
- **WHEN** 运行进入终态且结果可读取
- **THEN** 客户端在 Observation 对话区追加结构化结果摘要
- **AND** 展示可访问的产物信息（如有）

#### Scenario: Observation 文件树/预览交互
- **WHEN** 用户在 Observation 页展开文件树
- **THEN** 页面展示固定双栏文件树与预览窗口
- **AND** 点击文件节点后，预览区按局部渲染加载内容
- **AND** 预览内容来源为后端返回的 canonical preview payload

#### Scenario: E2E 与管理 UI 预览语义一致
- **WHEN** 同一路径文件在管理 UI 与 E2E 页面被打开
- **THEN** 两侧使用同源预览载荷语义
- **AND** 不因客户端本地依赖差异导致 markdown/json 渲染分叉
