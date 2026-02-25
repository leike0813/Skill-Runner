## 1. Contract and Spec Delta

- [x] 1.1 在 OpenSpec 中将 opencode 从“占位能力”转为“正式执行能力”语义
- [x] 1.2 补充 Harness 对 opencode 的正式执行/续跑行为约束
- [x] 1.3 同步 UI 引擎清单要求，覆盖 `/ui/engines` 与内联终端入口
- [x] 1.4 补充升级管理与 skill schema 的 opencode 合同约束
- [x] 1.5 补充 management/runtime parity 合同：动态模型缓存 + XDG 目录映射 + auth 导入规则

## 2. Runtime Adapter

- [x] 2.1 完成 `OpencodeAdapter` 的 start 命令构建
- [x] 2.2 完成 `OpencodeAdapter` 的 resume 命令构建（`--session=<id>`）
- [x] 2.3 完成 `OpencodeAdapter` 执行链路（配置、环境、prompt、进程采集）
- [x] 2.4 完成 `opencode_ndjson` 解析与 session handle 提取
- [x] 2.5 将 capability-unavailable 占位错误替换为正式实现行为

## 3. Model and Management

- [x] 3.1 `model_registry` 纳入 `opencode` 支持
- [x] 3.2 使用 `opencode models` 建立动态模型探测与缓存服务（启动/定时/run后刷新）
- [x] 3.3 校验 `opencode` 模型格式为 `<provider>/<model>` 并拒绝 `@effort`
- [x] 3.4 升级管理、CLI 管理、脚本入口支持 `opencode`
- [x] 3.5 opencode manifest 读取改为动态缓存兼容视图；snapshots 写入对 opencode 明确拒绝

## 4. UI and Runtime Peripheral

- [x] 4.1 `/ui/engines` 增加 `opencode` command profile
- [x] 4.2 cache key 增加 `opencode` 分支避免冲突
- [x] 4.3 FS diff ignore 规则纳入 `.opencode/`
- [x] 4.4 执行表单模型选择改为 provider/model 双下拉并兼容旧 `model` 字段提交
- [x] 4.5 RuntimeProfile 注入 XDG 目录映射以固定 opencode 配置/鉴权路径
- [x] 4.6 AgentCliManager 增加 opencode 基线配置与凭据导入规则（含 antigravity 账户文件）

## 5. Docs and Verification

- [x] 5.1 更新相关 docs 中的引擎支持矩阵与执行说明
- [x] 5.2 更新 adapter/model/management/UI/cache/harness 相关单测
- [x] 5.3 运行 runtime 必跑清单与本轮新增回归测试并通过
- [x] 5.4 更新容器化文档中的手工鉴权文件复制路径（新增 opencode）
