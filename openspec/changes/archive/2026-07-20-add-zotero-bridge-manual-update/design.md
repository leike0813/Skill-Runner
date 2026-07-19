## Context

有效 bundle 由 resolver 在 managed store 与内建 submodule 之间选择。现有 `state.json` 保存后台 updater 状态，但可能与实际 fallback 结果不一致；插件来源必须以 resolver 为准，版本必须从实际生效 manifest 的 `surface.version` 读取。当前发布 manifest 使用 `host-bridge.surface-release.v1`，CLI 工件声明位于 `releaseSet.cli.binaries`，wrapper 与 profile template 位于 `skills/zotero-bridge-cli/` 内。

后台 `check_once()` 当前在一次调用中完成远端查询、下载、校验、安装和激活。手动更新需要先查询、再由管理员明确安装，不能复制现有下载与校验实现。

## Goals / Non-Goals

**Goals:**

- 提供稳定、脱敏的插件管理状态 DTO。
- 查询阶段不下载、不激活；安装阶段只处理最近确认的 commit。
- 自动与手动更新共享锁、远端解析、下载、校验、安装和状态写入。
- 更新失败时继续使用上一 managed bundle 或内建 fallback。
- manifest 解析、路径和平台工件语义集中在单一 descriptor，安装前完成全部验证。
- Zotero 插件无效时不阻断其他 engine 的布局初始化。

**Non-Goals:**

- 通用插件市场、历史版本选择、降级、卸载或缓存清理。
- 热替换已经运行的 agent 子进程。
- 把现有文件安装流程改造成跨所有目标文件的完整事务。

## Decisions

### Stable management projection

新增投影函数只返回 `plugin_id`、`version`、`source`、`current_commit`、`auto_update_enabled`、`update_status`、`available_commit`、时间戳和脱敏错误。内部路径及 raw state 不进入公开 API。

版本缺失返回 `null`，不把缺少展示版本的有效 bundle 判为无效；来源仅在有效 managed bundle 实际生效时返回 `managed`。

### Canonical bundle descriptor

manifest adapter 生成不可变 descriptor，统一承载 schema、版本、wrapper/profile 相对路径、环境变量名和标准化的平台 binary/SHA256。validator、installer 与状态投影只消费该 descriptor；未知 schema、越界路径、缺失工件和 SHA256 不一致均拒绝继续。

installer 在第一次复制前完成 descriptor、wrapper、profile template、当前平台 binary 和 hash 校验。该边界避免无效候选在 managed agent home、profile 或 binary 目录留下部分安装结果；active pointer 仍在安装成功后切换。

### Bootstrap failure boundary

`AgentCliManager.ensure_layout()` 是插件失败的降级边界。Zotero 解析或安装失败时，它保留现有 bundle state 的 active 信息，写入结构化失败字段并记录日志，然后继续其他 engine 布局与 Claude MCP 同步。validator 与 installer 的直接调用保持 fail closed。

### Two-phase update workflow

`check_for_update()` 在共享锁内执行 `git ls-remote`，将结果写为 `up_to_date` 或 `update_available`。它不下载任何 archive。

`install_checked_update()` 要求 state 中存在候选 commit。安装前再次读取 remote head：若 branch 已移动则返回冲突并保留候选状态；否则按已确认 commit 下载、验证并激活。相同 commit 已激活时按幂等成功处理。

后台 `check_once()` 保持自动更新语义，但内部顺序改为查询后调用同一安装实现。`ENABLED=false` 只阻止后台 loop，管理员手动操作不受影响。

### API and authorization

三个接口均显式声明 `Depends(require_ui_basic_auth)`，因为 management router 本身没有全局 UI 鉴权依赖。成功统一返回插件状态 DTO；无候选或候选漂移返回 `409`，其他 updater 失败沿用 management API 的 `HTTPException`/`{"detail": ...}` 约定并保留可查询的失败状态。

### UI behavior

`/ui/settings` 服务端直出当前本地状态。卡片使用现有 card、readonly、status 和 button 样式；检查成功且有候选时启用安装按钮，操作中禁用按钮，结果通过 `aria-live` 呈现。来源只显示“内建”或“已下载更新”，不暴露 commit 或缓存路径给普通页面视图。

## Risks / Trade-offs

- branch 在检查后可能移动，因此安装必须重新检查并固定到已确认 commit。
- state 写着 `installed` 不代表 managed bundle 仍有效，因此 API 投影必须与 resolver 合并。
- 安装前验证可避免校验失败留下部分工件，但安装阶段本身并非跨 wrapper/profile/CLI 的完整事务；active pointer 只在所有安装步骤成功后切换。
- 自动与手动请求可能并发，必须由同一个 manager 实例和同一把锁串行。
