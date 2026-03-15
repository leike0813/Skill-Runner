## Design Summary

本 change 将“插件控制面”与“部署脚本实现面”解耦：

1. 插件只调用 `skill-runnerctl`。  
2. `skill-runnerctl` 在 local/docker 两种模式下提供统一命令语义。  
3. local 模式通过服务端租约心跳控制生命周期，避免 Zotero 异常退出导致残留进程。

## Decisions

- 本地模式默认绑定 `127.0.0.1`。
- 本地租约 TTL 默认 `60s`，推荐心跳间隔 `20s`。
- 本地模式不做自动重启；Docker 模式常驻由 compose 策略控制。
- 安装器只接受 release 固定版本并做 SHA256 校验。
- tag release 资产至少包含四件套：`docker-compose.release.yml`、其 `.sha256`、`skill-runner-<version>.tar.gz`、其 `.sha256`。
- 源码包由 CI 在 tag 构建时生成，且必须包含 `skills/*` 子模块内容。

## Runtime Lifecycle

### Local Mode

- `skill-runnerctl up --mode local` 启动服务。
- 插件调用 `POST /v1/local-runtime/lease/acquire` 获得 lease。
- 插件定时 `heartbeat` 保活。
- 插件正常退出时 `release`（可选再 `down`）。
- 若崩溃未 `release/down`，服务端在 lease 超时后自停。

### Docker Mode

- `skill-runnerctl up/down/status --mode docker` 仅作为 compose 控制与诊断入口。
- 生命周期以容器常驻为主，不使用 local lease API。

## Compatibility

- 现有业务 API、run 执行语义不变。
- `deploy_local.*` 仍可手动使用。
- 新增 API 仅在 `SKILL_RUNNER_RUNTIME_MODE=local` 可用，其他模式返回 `409`。
