## 设计

### Handshake API

`POST /v1/system/handshake` 是系统级协议能力查询接口，位于 `/v1/system/*` 下，与 management/system 现有认证策略保持一致。

响应固定使用：

- `schema = "zotero-agents.skillrunner-handshake.response.v1"`
- `backend.name = "Skill-Runner"`
- `backend.version = get_backend_version()`

协议能力第一版只表达布尔支持状态：

- `skillrunner.job.v1`: `supported=true`
- `skillrunner.sequence.v1`: `supported=false`
- unknown: `supported=false`

若请求没有提供 `requested_protocols`，接口返回当前已知协议清单。若提供了请求列表，接口按请求协议返回对应支持状态，并保留未知协议为 `false`。

### Version SSOT

`pyproject.toml` 的 `[project].version` 是版本单一事实源。运行时代码通过 `server/version.py` 读取版本：

1. 源码树存在 `pyproject.toml` 时优先读取 `[project].version`。
2. 安装包环境下 fallback 到 package metadata。
3. 极端失败时返回 `0.0.0`，避免系统启动失败。

FastAPI app metadata 与 handshake backend version 都使用同一 helper。

### Release guard

`scripts/bump_version.py` 提供两个稳定动作：

- 写入新 SemVer 到 `pyproject.toml`。
- 校验 tag `vX.Y.Z` 与 `pyproject.toml` 中 `X.Y.Z` 一致。

CI tag release 在构建源码包前执行校验；不一致时发布失败，避免再次产生漂移 release。
