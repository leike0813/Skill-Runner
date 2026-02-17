## 1. API 契约与模型

- [x] 1.1 在 `RunCreateRequest` 相关路径引入 `execution_mode`（默认 `auto`）
- [x] 1.2 更新 `options_policy` 与 allowlist，支持 `runtime_options.execution_mode`
- [x] 1.3 定义 pending/reply 的 Pydantic 模型

## 2. 路由实现

- [x] 2.1 新增 `GET /v1/jobs/{request_id}/interaction/pending`
- [x] 2.2 新增 `POST /v1/jobs/{request_id}/interaction/reply`
- [x] 2.3 实现 400/404/409 错误语义与返回体规范

## 3. 缓存与兼容

- [x] 3.1 interactive 模式跳过缓存命中
- [x] 3.2 interactive 模式不写入 cache_entries
- [x] 3.3 回归 auto 模式缓存路径无变化

## 4. 测试与文档

- [x] 4.1 单测覆盖 mode 校验、pending/reply 成功与失败分支
- [x] 4.2 回归测试：旧请求体（无 execution_mode）仍按 auto 执行
- [x] 4.3 更新 `docs/api_reference.md` 的 Jobs 章节
