## 1. Spec and Contract

- [x] 1.1 增加 `engine-runtime-config-layering` capability 规格，定义统一配置分层与优先级
- [x] 1.2 更新 `engine-adapter-runtime-contract`，纳入 opencode enforce 与模式化权限注入要求
- [x] 1.3 更新 `runtime-environment-parity`，明确 bootstrap 与 engine_default 的职责分离
- [x] 1.4 执行 `openspec validate engine-config-layering-and-opencode-permission-modes --type change`

## 2. Runtime Implementation

- [x] 2.1 在各引擎 Adapter/ConfigManager 中接入 `engine_default` 层（最低优先级）
- [x] 2.2 在 opencode Adapter 中接入 `opencode_enforced.json`
- [x] 2.3 在 opencode 项目级配置注入中按执行模式追加 `permission.question`：
- [x] 2.3.1 auto -> `deny`
- [x] 2.3.2 interactive -> `allow`
- [x] 2.4 保持现有 bootstrap 行为不变（仅初始化用途）

## 3. Regression and Docs

- [x] 3.1 更新配置组装相关单测（四引擎分层优先级、opencode 模式注入）
- [x] 3.2 更新缓存键/运行目录忽略相关测试（若配置文件参与 diff 采样）
- [x] 3.3 更新 engine 配置组装文档（core components / execution flow / containerization / dev guide）
- [x] 3.4 回归现有命令构建与交互续跑测试，确保无行为倒退
