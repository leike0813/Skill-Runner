## 1. Adapter Runtime Contract

- [x] 1.1 扩展 `EngineAdapter` 抽象接口，定义统一的 start/resume 命令构建契约
- [x] 1.2 在 Adapter 基类中定义统一 runtime 流解析返回结构与类型约束
- [x] 1.3 新增/调整 Adapter 注册与获取入口，支持主服务与 Harness 共享调用

## 2. Engine-Specific Migration

- [x] 2.1 将 codex 的 runtime 流解析逻辑迁移至 `CodexAdapter`
- [x] 2.2 将 gemini 的 runtime 流解析逻辑迁移至 `GeminiAdapter`
- [x] 2.3 将 iflow 的 runtime 流解析逻辑迁移至 `IFlowAdapter`
- [x] 2.4 新增临时 `OpencodeAdapter` 并迁移可复用解析逻辑
- [x] 2.5 为 `OpencodeAdapter` 未实现执行能力提供结构化 capability-gated 错误

## 3. Runtime Protocol Refactor

- [x] 3.1 重构 `runtime_event_protocol`，改为调用 Adapter 解析接口获取标准解析结果
- [x] 3.2 移除通用协议层中的引擎专用解析分支，保留事件组装/去重/度量职责
- [x] 3.3 校验 RASP/FCMP 输出字段与既有协议保持兼容

## 4. Command Profile Defaults

- [x] 4.1 新增 `server/assets/configs/engine_command_profiles.json`
- [x] 4.2 新增 profile 加载与校验服务，定义默认参数与显式参数合并顺序
- [x] 4.3 在 API 编排链路接入 profile 默认参数注入
- [x] 4.4 确保 Harness 链路禁用 profile 注入

## 5. Harness Shared Execution Path

- [x] 5.1 重构 Harness start 路径为调用 Adapter start 命令构建接口
- [x] 5.2 重构 Harness resume 路径为调用 Adapter resume 命令构建接口
- [x] 5.3 重构 Harness runtime 解析路径为调用 Adapter 解析接口
- [x] 5.4 保持 `--translate` 为 Harness 视图参数且不透传给引擎命令

## 6. Tests and Regression

- [x] 6.1 新增 Adapter 命令构建单元测试（API with profile / Harness without profile）
- [x] 6.2 新增 Adapter runtime 解析单元测试（codex/gemini/iflow/opencode）
- [x] 6.3 更新 `runtime_event_protocol` 相关测试，验证其仅做通用组装
- [x] 6.4 更新 Harness 单元测试，验证其复用 Adapter 执行链路
- [x] 6.5 运行全量单元测试并修复回归

## 7. Verification

- [x] 7.1 执行 OpenSpec 校验并确认 change 可进入实现
- [x] 7.2 补充相关文档（架构边界与参数来源说明）
