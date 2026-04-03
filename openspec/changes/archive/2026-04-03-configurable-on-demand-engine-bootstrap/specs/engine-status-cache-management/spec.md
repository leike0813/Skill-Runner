## MODIFIED Requirements
### Requirement: Engine 版本读取 MUST 对缺失或损坏缓存降级
系统 MUST 在缓存缺失、损坏或部分引擎缺项时返回稳定结果，而不是现场探测。

#### Scenario: subset bootstrap keeps uninstalled engines readable
- **WHEN** bootstrap/install 仅对 engine 子集执行 ensure
- **THEN** 未请求安装的 engine 在缓存/UI/API 中仍以稳定结构呈现
- **AND** 未安装 engine 表现为 `present=false` 与空版本
- **AND** 读路径不会因其缺失而触发临时安装或探测
