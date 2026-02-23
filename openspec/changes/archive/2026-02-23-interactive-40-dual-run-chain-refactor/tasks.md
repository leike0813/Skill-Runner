## 1. Spec Baseline

- [x] 1.1 新增 `dual-run-chain-architecture` 规范，定义双链路独立/共用边界
- [x] 1.2 更新 `interactive-job-api`，要求常规链路复用统一核心
- [x] 1.3 更新 `ephemeral-skill-upload-and-run`，要求临时链路复用统一核心并保留专属职责
- [x] 1.4 更新 `management-api-surface`，补充 source 能力矩阵约束

## 2. Source Adapter Abstraction

- [x] 2.1 引入 `RunSourceAdapter` 接口（installed/temp）
- [x] 2.2 实现 source 能力矩阵字段，并约束 `pending/reply/history/range` 在 installed/temp 均为可用
- [x] 2.3 实现 source 专属 cache namespace 与扩展 cache 因子注入

## 3. Shared Core Refactor

- [x] 3.1 提炼 create 阶段共用服务（runtime/model/mode 校验与 request 初始化）
- [x] 3.2 提炼 upload-start 阶段共用服务（manifest/cache/schedule）
- [x] 3.3 提炼 run 读路径 facade（状态/日志/事件/结果/产物/bundle/取消）
- [x] 3.4 统一错误映射与状态回写策略
- [x] 3.5 提炼统一交互服务（pending/reply）并在双链路复用
- [x] 3.6 提炼统一历史读取服务（events/history + logs/range）并在双链路复用

## 4. Router Integration

- [x] 4.1 `jobs.py` 改为 source=installed 绑定统一核心
- [x] 4.2 `temp_skill_runs.py` 改为 source=temp 绑定统一核心
- [x] 4.3 为 temp 链路补齐与常规链路对等的 `pending/reply/history/range` 外部端点
- [x] 4.4 保持现有外部 API 路径与语义兼容

## 5. Tests and Verification

- [x] 5.1 新增 source adapter 单元测试（能力矩阵、cache namespace、skill 解析）
- [x] 5.2 新增双链路一致性测试（pending/reply/history/range 必须同构）
- [x] 5.3 新增双链路差异性测试（仅 source 专属能力）
- [x] 5.4 运行全量单元测试并修复回归
- [x] 5.5 执行 OpenSpec 校验并推进到 apply-ready
