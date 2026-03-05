## 1. OpenSpec Artifacts

- [x] 1.1 完成 proposal/design/tasks 与 delta specs，明确“非 debug 白名单 + debug 黑名单 + run explorer 复用黑名单”合同。

## 2. Rule Files and Filter Service

- [x] 2.1 新增 `run_bundle_allowlist_non_debug.ignore` 与 `run_bundle_denylist_debug.ignore` 两份规则文件。
- [x] 2.2 新增统一过滤服务，支持白名单/黑名单匹配与路径规范化。
- [x] 2.3 从现有非 debug 实现抽取默认白名单规则（`result/result.json`、`artifacts/**`）。

## 3. Bundle and Explorer Integration

- [x] 3.1 改造 `RunBundleService`：非 debug 走白名单、debug 走黑名单。
- [x] 3.2 改造 run explorer 文件树与文件预览：复用 debug 黑名单并完全隐藏命中项。
- [x] 3.3 保持公开 API 路径不变，仅收敛可见文件集合。

## 4. UI Tree Folding

- [x] 4.1 管理 UI 文件树默认全折叠，支持目录点击展开/收起。
- [x] 4.2 e2e client 文件树实现与管理 UI 保持一致行为。

## 5. Tests

- [x] 5.1 新增/更新 bundle manifest 测试，覆盖白名单与黑名单路径过滤。
- [x] 5.2 新增/更新 run observability 测试，覆盖 run tree/preview 过滤。
- [x] 5.3 新增/更新管理 UI 与 e2e client 文件树默认折叠回归测试。
