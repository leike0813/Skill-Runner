## ADDED Requirements

### Requirement: E2E 客户端代理 MUST 支持 run bundle 下载透传
E2E 客户端代理层 MUST 提供 run bundle 下载透传能力，以稳定消费后端 run bundle API。

#### Scenario: proxy returns backend bundle as attachment
- **WHEN** 客户端调用 `/api/runs/{request_id}/bundle/download`
- **THEN** 代理 MUST 从后端获取 run bundle 二进制
- **AND** 以 zip 附件响应返回给浏览器

#### Scenario: proxy preserves backend error semantics
- **WHEN** 后端返回 run 不存在、bundle 生成失败或网络不可达
- **THEN** 代理 MUST 返回受控错误响应
- **AND** 错误映射行为与现有 E2E 代理一致
