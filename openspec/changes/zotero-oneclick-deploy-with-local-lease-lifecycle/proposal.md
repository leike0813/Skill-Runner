## Why

当前仓库已有本地部署脚本与容器部署路径，但缺少面向 Zotero 插件的一键控制协议与“异常退出自动回收”能力。  
仅依赖插件在退出时调用 `down` 不可靠：进程崩溃/强杀时会残留本地服务。  
同时，插件侧需要稳定调用面，不能直接耦合 `deploy_local.*` 的实现细节。

## What Changes

- 新增本地运行租约 API（acquire/heartbeat/release/status），并在本地模式下启用 TTL（默认 60s）超时自停。
- 新增标准控制命令 `skill-runnerctl`（install/up/down/status/doctor），作为插件唯一调用入口。
- 新增跨平台安装器脚本（Linux/macOS + Windows），采用 release 固定版本与 SHA256 校验。
- 保留 `deploy_local.sh/.ps1` 作为底层能力，不再作为插件集成入口。
- 文档新增 Zotero 插件集成契约，明确调用时序与错误语义。

## Capabilities

### Modified Capabilities

- `local-deploy-bootstrap`: 增加插件友好的控制入口与安装器能力。
- `interactive-job-api`: 增加本地运行租约 API 语义，用于本地生命周期控制。
