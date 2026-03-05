## Context

当前实现里：

- `RunBundleService` 在 `debug=true` 直接 `rglob("*")` 收集文件，缺少排除机制。
- run 文件树与文件预览没有统一过滤，`node_modules` 会污染管理 UI 和 e2e 客户端体验。
- 文件树默认展开，目录层级深时可读性差。

本变更目标是把“打包与浏览过滤规则”收敛为同一套后端规则源，并统一前端树交互默认态。

## Decisions

### 1) 过滤规则按职责拆为两个文件

- `server/assets/configs/run_bundle_allowlist_non_debug.ignore`
  - 非 debug bundle 白名单
  - 首版规则直接抽取现有行为：
    - `result/result.json`
    - `artifacts/**`
- `server/assets/configs/run_bundle_denylist_debug.ignore`
  - debug bundle 黑名单
  - 默认至少包含：
    - `**/node_modules/`
    - `**/node_modules/**`

### 2) Run explorer 复用 debug 黑名单

后端 run 文件树与文件预览统一复用 `run_bundle_denylist_debug.ignore`，对命中规则的目录和文件做完全隐藏：

- 目录项不返回
- 子文件不返回
- 手工请求被过滤路径的预览时返回可诊断错误（400/404）

### 3) 统一过滤服务（单一实现）

新增后端过滤服务（建议路径：`server/services/orchestration/run_file_filter_service.py`）：

- 加载两份 ignore 规则文件
- 提供白名单/黑名单匹配函数
- 提供路径规范化与目录前缀命中过滤
- 为 bundle、run tree、run preview 提供统一判定 API

避免在 bundle、observability、UI 路由中复制规则解析逻辑。

### 4) 文件树默认折叠（管理 UI + e2e 一致）

- 管理 UI `run_detail.html` 与 e2e `run_observe.html` 都采用目录默认折叠。
- 点击目录节点时本地展开/收起。
- 文件项保持现有预览行为。

## Flow Changes

### Bundle 打包

1. `RunBundleService.bundle_candidates(...)`
2. `debug=false`：
   - 仅允许匹配非 debug 白名单的文件进入 candidates
3. `debug=true`：
   - 先按现有 debug 候选枚举
   - 再应用 debug 黑名单排除（含任意层级 `node_modules`）
4. 生成 zip 与 manifest，二者保持一致过滤结果

### Run 文件树与预览

1. run detail 读取目录树时，服务端先应用 debug 黑名单
2. 被过滤目录与文件不进入返回 entries
3. run file preview 请求先做同规则校验，命中过滤规则直接拒绝

## Backward Compatibility

- 非 debug bundle 输出范围保持与当前语义一致，仅改为规则文件显式表达。
- debug bundle 与 run explorer 将新增排除项（`node_modules`），属于有意行为收敛。
- 不变更公开 HTTP 路径；仅调整响应内容中的可见文件集合与前端默认展开状态。

## Risks and Mitigations

- 风险：规则表达不当导致误过滤结果文件。
  - 规避：非 debug 采用显式白名单，且以现有行为为初始规则。
- 风险：run explorer 与 bundle 规则漂移。
  - 规避：run explorer 固定复用 debug 黑名单同一文件，不复制规则。
- 风险：前端折叠状态与历史逻辑冲突。
  - 规避：仅改变初始展开状态，不改变文件预览接口与数据格式。

## Validation Plan

- 单测验证非 debug 白名单与 debug 黑名单行为。
- 单测验证 run tree / preview 对被过滤路径隐藏与拒绝。
- UI 相关测试验证目录默认折叠与点击展开行为（管理端 + e2e 端一致）。
