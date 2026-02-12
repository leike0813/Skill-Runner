## 1. API 与模型

- [x] 1.1 在 `RunCreateRequest` 中新增顶层 `input` 字段（`Dict[str, Any]`）
- [x] 1.2 确保请求落盘（request/input.json）包含 `input`
- [x] 1.3 保持现有 `parameter` 语义不变

## 2. Schema 与校验逻辑

- [x] 2.1 在 schema validator 中增加 input source 解析（`x-input-source`）
- [x] 2.2 默认 source 行为设为 `file`（向后兼容）
- [x] 2.3 创建阶段校验 inline required 字段
- [x] 2.4 上传/执行阶段校验 file required 字段
- [x] 2.5 `build_input_context` 支持 mixed input（路径 + JSON 值）

## 3. 编排与触发

- [x] 3.1 在 jobs router 中支持“仅 inline required 时创建后直接执行”
- [x] 3.2 保持“存在 file required 时需 upload 后执行”行为
- [x] 3.3 错误码与现有 jobs 语义保持一致

## 4. 缓存

- [x] 4.1 在 cache key builder 中新增 `inline_input_hash`
- [x] 4.2 覆盖测试：inline 变化导致 cache key 变化

## 5. 测试

- [x] 5.1 单测：纯 file 输入（回归）
- [x] 5.2 单测：纯 inline 输入
- [x] 5.3 单测：mixed 输入（file + inline）
- [x] 5.4 单测：inline required 缺失时 create 400
- [x] 5.5 跑 mypy 和目标 pytest

## 6. 文档

- [x] 6.1 更新 `docs/file_protocol.md`（新增 mixed input 协议）
- [x] 6.2 更新 `docs/api_reference.md`（`POST /v1/jobs` 新增 `input` 示例）
- [x] 6.3 更新相关 skill 指南中 input/parameter 边界说明
