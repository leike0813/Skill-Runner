## Context

当前 interactive 模式开关是“请求侧能力”，但 Skill 本身没有声明“是否支持 interactive”。  
这会造成以下问题：
- 前端无法在提交前判断 Skill 是否支持目标模式；
- 后端无法拒绝不兼容请求；
- Skill 包规范无法表达执行模式边界。

## Goals

1. 为 Skill 增加可执行模式声明（runner.json）。
2. 在 run 创建阶段做强校验，阻止不被 Skill 支持的模式请求。
3. 在安装与临时上传链路统一校验该声明字段。
4. 提供平滑兼容，避免老 Skill 一次性全部不可用。

## Non-Goals

1. 不在本 change 设计更细粒度权限（如按参数/阶段限制模式）。
2. 不改变 interactive 状态机与 adapter 协议。
3. 不在本 change 改造 UI，只定义 API/Skill 合同。

## Prerequisite

- `interactive-00-api-mode-and-interaction-contract`

## Design

### 1) runner.json 声明字段

在 `assets/runner.json` 增加：
- `execution_modes: string[]`

约束：
- 必须是非空数组；
- 值仅允许 `auto`、`interactive`；
- 推荐声明：
  - 纯自动 Skill：`["auto"]`
  - 双模式 Skill：`["auto", "interactive"]`

### 2) 提交流程准入校验

在 `POST /v1/jobs` 与临时 Skill 提交流程中，按以下顺序校验：
1. 解析请求模式（缺省仍是 `auto`）。
2. 读取 Skill 声明模式集合。
3. 若请求模式不在集合中，返回 400，错误码 `SKILL_EXECUTION_MODE_UNSUPPORTED`。

### 3) 安装与临时上传校验

`skill-package-install` 与 `ephemeral-skill-validation` 同步新增验证：
- `runner.json.execution_modes` 缺失、空、含非法值时拒绝。

### 4) 兼容策略

为降低对历史 Skill 的破坏：
- 运行时：若已安装 Skill 缺失 `execution_modes`，临时按 `["auto"]` 解释，并记录 deprecation 警告。
- 上传/更新：新包必须显式声明 `execution_modes`（不再接受缺失）。

说明：
- 该兼容仅用于存量 Skill 运行，不用于新包入库。

### 5) 错误与可观测

新增错误码：
- `SKILL_EXECUTION_MODE_UNSUPPORTED`

建议错误消息：
- `Skill '<id>' does not support execution_mode '<mode>'`

日志字段建议：
- `skill_id`
- `requested_execution_mode`
- `declared_execution_modes`

## Risks & Mitigations

1. **风险：旧 Skill 缺失字段导致回归**
   - 缓解：运行时回退到 `["auto"]`，并在日志提示迁移。
2. **风险：请求侧与 Skill 侧模式不一致导致报错增多**
   - 缓解：在文档中明确模式声明约束，并通过错误码给出可诊断信息。
3. **风险：多入口校验不一致**
   - 缓解：复用同一校验函数，避免在 jobs/temp-skill-runs 分别实现。
