## 1. OpenSpec

- [x] 1.1 新建 change `add-workspace-file-bindings`
- [x] 1.2 更新 `interactive-job-api` delta spec
- [x] 1.3 更新 `reused-workspace-skill-runs` delta spec
- [x] 1.4 更新 `run-file-contract` delta spec
- [x] 1.5 运行 `openspec validate add-workspace-file-bindings --strict`

## 2. 后端实现

- [x] 2.1 新增 workspace file binding materialization 服务
- [x] 2.2 扩展 `OptionsPolicy._validate_workspace()` 基础 shape 校验
- [x] 2.3 在 create flow 支持 bindings 满足 file input 后直接排队
- [x] 2.4 在 upload flow 解压后、manifest/hash 前 materialize bindings
- [x] 2.5 确保 cache/input manifest 包含 materialized 文件

## 3. 测试

- [x] 3.1 覆盖 OptionsPolicy 合法/非法 `file_bindings`
- [x] 3.2 覆盖 create + reuse + file_bindings 无需 upload
- [x] 3.3 覆盖 upload zip 与 binding 冲突时 binding 覆盖
- [x] 3.4 覆盖 cache key 随绑定文件内容变化
- [x] 3.5 覆盖 source request、workspace、路径和重复绑定失败场景

## 4. 文档

- [x] 4.1 更新 `docs/api_reference.md`
- [x] 4.2 更新 `docs/file_protocol.md`
- [x] 4.3 更新 `docs/workspace_reuse_and_file_namespace.md`
