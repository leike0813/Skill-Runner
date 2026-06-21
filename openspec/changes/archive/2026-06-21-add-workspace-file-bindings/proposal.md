## 为什么要做

当前 workspace reuse 只能复用同一物理 workspace 的运行目录和输出命名空间，但新的请求仍需要客户端重新上传 file input。
这使“上游 run 产物作为下游 run 文件输入”的工作流缺少后端协议支持：前端无法安全地把服务端已有文件重新挂载到当前 run 的 `uploads/`。

## 变更目标

新增 `runtime_options.workspace.file_bindings`，允许客户端在 `mode: "reuse"` 时声明：

- 从同一物理 workspace 内的某个 succeeded request 读取 `source_path`
- 在当前 run 执行前 materialize 到 `uploads/<target_path>`
- 保持 `input[input_key]` 为 uploads-relative path，不改变现有 skill file input 语义
- 让 materialized 文件参与 input manifest 和 cache key 计算

## 变更范围

- API 合同：`POST /v1/jobs` 的 `runtime_options.workspace` 增加 `file_bindings`。
- 校验：绑定对象 shape、重复 input/target、路径安全、source request 状态、同 workspace 约束。
- create/upload 流程：在 manifest/hash 计算前 materialize 绑定文件。
- 文件系统行为：非 Windows 优先硬链，失败回退复制；Windows 使用复制；重复目标由 binding 覆盖。
- 文档与测试：覆盖请求协议、路径规则、缓存语义和失败场景。
