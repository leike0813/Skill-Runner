## 背景

Skill file input 的现有执行语义是从 `run_dir/uploads/<input value>` 解析文件。
workspace reuse 已能让新 run 使用旧 run 所在物理 workspace，但没有把旧 workspace 文件安全投影到当前 run `uploads/` 的机制。

本设计新增服务端 materialization 协议，而不是让客户端下载再上传同一文件。

## 设计目标

1. 复用 workspace 时支持服务端文件 handoff。
2. 不改变 skill adapter/schema validator 的执行期解析语义。
3. materialized 文件进入 input manifest/cache key，避免错误缓存命中。
4. 所有路径都保持 workspace-relative 或 uploads-relative，禁止越界。

## 请求协议

`runtime_options.workspace.mode` 为 `reuse` 时可携带：

```json
{
  "file_bindings": [
    {
      "input_key": "artifact_file",
      "source_request_id": "<request in same workspace>",
      "source_path": "runtime/file.json",
      "target_path": "inputs/artifact_file/file.json"
    }
  ]
}
```

约束：

- `input[input_key]` 必须存在且等于 `target_path`。
- `source_path` 是 workspace-relative path。
- `target_path` 是 uploads-relative path。
- 同一请求内 `input_key` 和 `target_path` 均不得重复。
- `source_request_id` 必须解析为 succeeded request，且物理 `workspace_dir` 与当前 reuse workspace 相同。

## Materialization

create flow 和 upload flow 都先构造 staging uploads，然后在 manifest/hash 计算前 materialize bindings：

- create flow：如果 file input 能由 bindings 满足，不进入 pending upload。
- upload flow：先解压上传 zip，再 materialize bindings；同 target 时 binding 覆盖 zip 文件。
- cache/input manifest 使用 materialized 后的 staging uploads。
- cache miss 后 staging uploads 被复制到 run `uploads/`。

文件落地策略：

- Windows：复制。
- 非 Windows：优先硬链，硬链失败后回退复制并记录日志。
- 若 `uploads/<target_path>` 已存在且为文件，先覆盖。
- 若目标位置已有目录，返回 4xx，不创建半成品 run。

## 失败语义

以下场景返回 4xx：

- `file_bindings` 不是数组或元素不是对象。
- 绑定缺字段、字段非字符串或空字符串。
- 重复 `input_key` 或重复 `target_path`。
- `input[input_key]` 缺失或不等于 `target_path`。
- `source_request_id` 不存在、未成功或缺少 workspace metadata。
- source 与当前 reuse workspace 不同。
- source/target path 绝对、空、`.`、`..` 或越界。
- source 不存在、是目录或 target 已有目录。

## 组件改动

1. `server/services/orchestration/workspace_file_binding_service.py`
   - 集中处理 binding 解析、路径校验、同 workspace 校验和 materialization。

2. `server/services/platform/options_policy.py`
   - 对 `runtime_options.workspace.file_bindings` 做基础 shape 校验。

3. `server/routers/jobs.py`
   - create flow 在 staging uploads 中 materialize bindings，并基于 staging 生成 manifest/cache key。
   - upload flow 在 zip 解压后、manifest 计算前 materialize bindings。

4. 文档
   - 更新 API、文件协议和 workspace reuse 文档。

## 风险与缓解

- 风险：绑定文件未进入 cache key 导致错误命中。  
  缓解：所有 flow 都在 materialize 后调用 `build_input_manifest`。

- 风险：跨 workspace 读取造成数据隔离破坏。  
  缓解：source request 与 reuse source 必须解析到同一物理 `workspace_dir`。

- 风险：路径校验分散导致行为不一致。  
  缓解：新增服务集中校验 source 和 target path。
