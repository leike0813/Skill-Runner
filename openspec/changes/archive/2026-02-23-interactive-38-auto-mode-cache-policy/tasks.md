## 1. Spec Alignment

- [x] 1.1 更新 `ephemeral-skill-upload-and-run`：临时链路缓存策略改为 execution_mode 分流（auto 可缓存，interactive 禁用）
- [x] 1.2 更新 `ephemeral-skill-upload-and-run`：新增“上传 skill 压缩包哈希参与 auto 缓存键”要求
- [x] 1.3 更新 `mixed-input-protocol`：显式声明全链路 cache lookup/write-back 为 auto-only
- [x] 1.4 更新 `output-json-repair`：repair-success 缓存语义限定于缓存可用模式

## 2. Backend Implementation

- [x] 2.1 在临时链路构建缓存键时，新增 `temp_skill_package_hash`（对上传压缩包整体字节流哈希）
- [x] 2.2 在 `server/routers/temp_skill_runs.py` 接入 auto 模式 cache lookup/write-back 分支
- [x] 2.3 维持 `runtime_options.no_cache=true` 最高优先级禁用缓存
- [x] 2.4 保持 `interactive` 模式临时链路与常规链路一致：不读不写缓存
- [x] 2.5 对 cache key builder 增加可复用扩展点，避免常规与临时链路重复拼 key 逻辑
- [x] 2.6 常规链路与临时链路使用独立缓存表（`cache_entries` / `temp_cache_entries`）
- [x] 2.7 orchestrator 按链路将成功结果写入对应缓存表

## 3. Tests

- [x] 3.1 新增/更新单元测试：临时链路 auto 模式可命中缓存
- [x] 3.2 新增/更新单元测试：临时链路 interactive 模式不读写缓存
- [x] 3.3 新增/更新单元测试：临时链路 `no_cache=true` 时禁用缓存
- [x] 3.4 新增/更新单元测试：临时链路同输入不同 skill 压缩包产生不同 cache key
- [x] 3.5 新增/更新单元测试：临时链路同输入同 skill 压缩包可复用 cache key
- [x] 3.6 回归常规链路测试：interactive 不缓存守护不退化
- [x] 3.7 新增 run store 单测：常规/临时缓存表同 key 隔离

## 4. Documentation and Verification

- [x] 4.1 更新 API/开发文档中的缓存策略说明（明确 auto-only 与临时包哈希因子）
- [x] 4.2 运行全量单元测试并修复回归
- [x] 4.3 执行 OpenSpec 校验并确认 change 达到 apply-ready
