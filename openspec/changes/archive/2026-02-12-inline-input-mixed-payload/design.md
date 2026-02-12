## 背景

`input` 在当前实现里只从 `uploads/` 文件系统读取，且上下文构建时默认值为路径字符串。
这导致“非文件业务输入”只能被塞进 `parameter`，语义混乱并增加后续技能转换复杂度。

本设计将 `input` 扩展为混合来源：

- `file`：上传文件并映射为路径（兼容现状）
- `inline`：请求体 `input.<key>` 直接提供 JSON 值（新增）

## 设计目标

1. 保持现有文件输入能力和旧技能兼容。
2. 支持在请求体直接提交 inline input。
3. 明确 `input` 与 `parameter` 语义边界。
4. 不新增全局开关，默认可用。

## 关键决策

### 决策 1：请求体新增 `input` 顶层字段

- `RunCreateRequest` 新增：`input: Dict[str, Any] = {}`
- `parameter` 继续仅用于控制参数

理由：
- 避免把业务输入错误归类到 `parameter`
- 让 `input` 上下文与技能语义一致

### 决策 2：`input.schema.json` 增加来源标注

每个 input 字段支持扩展字段：

- `x-input-source: "file"`（默认）
- `x-input-source: "inline"`

未标注时默认按 `file`，保证历史技能零改动。

### 决策 3：分阶段校验与执行触发

- 创建请求阶段：
  - 校验 inline required 字段（缺失即 400）
  - file required 继续等待上传阶段
- 上传阶段/执行阶段：
  - 校验 file required 字段和文件存在性

触发策略：
- 若仅有 inline required（无 file required），请求创建后可直接执行。
- 若存在 file required，仍需上传后执行。

### 决策 4：缓存键加入 inline 输入哈希

缓存键新增 `inline_input_hash`（规范化 JSON 后哈希）。

理由：
- 避免“文件相同但 inline 内容不同”误命中缓存。

## 组件改动

1. `server/models.py`
- `RunCreateRequest` 增加 `input` 字段。

2. `server/services/schema_validator.py`
- 新增读取 input 字段来源的能力（按 `x-input-source` 拆分 key）。
- `build_input_context` 输出类型改为 `Dict[str, Any]`：
  - file -> 绝对路径字符串
  - inline -> 原始 JSON 值

3. `server/services/job_orchestrator.py`
- input 校验拆分：
  - inline 用请求体 `input` 校验
  - file 用 `uploads/` 虚拟字典校验

4. `server/routers/jobs.py`
- 保存 `input` 到 request payload。
- 创建阶段可识别“是否需要等待上传”。

5. `server/services/cache_key_builder.py`
- cache key 组成项新增 `inline_input_hash`。

6. 文档
- 更新 `docs/file_protocol.md` 与 `docs/api_reference.md`。

## 风险与缓解

- 风险：旧技能误将 inline 字段当 file 处理。  
  缓解：默认 `file`，仅显式 `x-input-source:inline` 才走 inline 流程。

- 风险：inline input 体积过大影响性能。  
  缓解：沿用网关/应用层请求体限制，不在本变更新增全局特性开关。

- 风险：prompt 模板中 `input` 值类型不再全是字符串路径。  
  缓解：更新文档，要求技能模板在引用 inline 字段时按 JSON 语义处理。

## 回滚策略

若出现回归，可回滚至“input 仅文件来源”：

1. 移除请求体 `input` 字段读取。
2. 忽略 `x-input-source:inline`。
3. 取消 `inline_input_hash` 参与 cache key。
