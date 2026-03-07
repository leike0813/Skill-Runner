## Why

当前 Skill Runner 默认将内嵌 ttyd 端口设置为 `7681`，与宿主机常见的 `ttyd.service` 默认端口冲突，导致容器端口发布失败或 UI shell 无法访问。  
需要将该端口策略收敛为高位默认端口，并在本地部署、容器部署、文档示例中保持单一真源，避免用户踩坑。

## What Changes

- 将 `UI_SHELL_TTYD_PORT` 默认值从 `7681` 调整为更不易冲突的高位端口（`17681`）。
- 统一容器部署端口映射为同号映射（`17681:17681`），并在 compose 中明确注释“不要拆分 host/container 端口”。
- 全仓同步本地部署脚本、compose 模板、README 多语言示例与说明，确保端口语义一致。
- 保留 `UI_SHELL_TTYD_PORT` 单配置项，不新增 public/internal 双端口配置，降低误配置复杂度。
- 更新相关单测断言以匹配新默认值与部署约束。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `local-deploy-bootstrap`: 本地与容器部署文档/脚本中的 ttyd 默认端口与映射规则调整为统一高位端口。
- `ui-engine-management`: 管理 UI 内嵌终端链路采用统一端口真源，默认规避系统 `ttyd.service` 冲突。
- `ui-engine-inline-terminal`: 内嵌终端会话管理的默认端口策略变更为高位端口。

## Impact

- Affected code:
  - `server/services/ui/ui_shell_manager.py`
  - `scripts/deploy_local.sh`
  - `docker-compose.yml`
  - `docker-compose.release.tmpl.yml`
  - `README.md`
  - `README_CN.md`
  - `README_JA.md`
  - `README_FR.md`
  - `tests/unit/test_ui_shell_manager.py`
- API impact: None.
- Protocol impact: None.
