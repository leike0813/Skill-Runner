## Context

管理 UI 的内嵌 terminal 通过独立 ttyd 网关对外暴露。当前默认端口 `7681` 与宿主机常驻 `ttyd.service` 高概率冲突。  
冲突在容器模式下会直接导致 `ports` 发布失败，在本地模式下会触发端口探测回退并产生环境差异。

## Goals / Non-Goals

**Goals**
- 让 Skill Runner ttyd 默认端口与系统 ttyd 默认端口解耦。
- 保证本地部署、容器部署、文档示例、测试断言使用统一端口语义。
- 保持单配置项 `UI_SHELL_TTYD_PORT`，避免双端口配置带来的误用。

**Non-Goals**
- 不引入 `UI_SHELL_TTYD_PUBLIC_PORT` 这类新配置。
- 不改 UI shell 会话协议、鉴权流程、路由路径。
- 不改 FCMP/RASP/runtime 协议语义。

## Decisions

### 1) 默认端口改为固定高位端口

- `UI_SHELL_TTYD_PORT` 默认值由 `7681` 改为 `17681`。
- 该默认值在 `ui_shell_manager` 作为单一代码真源。

### 2) Compose 强制同号映射

- `docker-compose.yml` 与 `docker-compose.release.tmpl.yml` 统一为：
  - `17681:17681`
  - `UI_SHELL_TTYD_PORT=17681`
- 在 compose 文件端口块增加注释：不要单独修改 host/container 一侧端口。

### 3) 文档与脚本全仓同步

- README（EN/CN/JA/FR）所有 docker run / compose 端口示例同步到 `17681`。
- `scripts/deploy_local.sh` 显式导出默认 `UI_SHELL_TTYD_PORT=17681`，确保本地部署与容器部署一致。

### 4) 测试同步

- 更新 `tests/unit/test_ui_shell_manager.py` 中对默认 ttyd 端口的断言值。

## Risks / Trade-offs

- [Risk] 用户历史脚本仍写死 `7681`。  
  → Mitigation: README 与 compose 注释明确迁移方式；仍支持环境变量覆盖。

- [Risk] 某些环境 `17681` 仍可能冲突。  
  → Mitigation: 本地模式继续保留向上探测回退逻辑；容器模式提供清晰错误提示和可覆盖配置。

## Migration Plan

1. 先改代码默认值与 compose 端口映射。
2. 再同步部署脚本和多语言文档。
3. 更新单测断言并运行 targeted 测试。
4. `openspec validate` 通过后进入归档准备。
