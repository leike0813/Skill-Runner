## Why

System Console 目前只能管理日志与数据重置，管理员无法确认当前 Zotero Bridge CLI 插件的实际版本和来源，也无法在自动更新之外主动检查并安装更新。现有后台 updater 已具备远端查询、校验和安装能力，但查询与安装耦合，且没有受保护的管理 API 或 UI。

## What Changes

- 在 System Console 日志设置上方增加 Zotero Bridge CLI 插件状态卡片。
- 展示实际生效 bundle 的版本和来源（内建或已下载更新）。
- 提供受 Basic Auth 保护的本地状态、手动检查更新和安装已确认更新接口。
- 将后台 updater 拆分为可复用的查询与安装原语，后台自动更新继续复用相同链路。
- 为候选 commit 增加持久化、并发互斥、漂移拒绝、幂等安装与失败回退语义。
- 同步管理 API、Web UI、managed plugin 规格、文档、国际化和测试。

## Impact

- 扩展 Zotero Bridge CLI managed bundle 状态与更新服务。
- 新增 `/v1/management/system/plugins/zotero-bridge-cli*` 管理 API。
- 修改 `/ui/settings` 首屏结构，不改变现有日志设置和 data reset 行为。
- 不改变 runtime FCMP/RASP 协议、正在运行的 agent 进程或 Zotero 外部插件合同。
