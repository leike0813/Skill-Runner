# Design

## Overview

本次重构将“文件协议的真源”统一为：

- **artifact**：output JSON 中被 `x-type: artifact|file` 标记的字段
- **file input**：`POST /v1/jobs` 请求体中对应 file 字段的 `uploads/` 相对路径

也就是说：

- 不再把 `artifacts/<pattern>` 作为 artifact 正确性的真源
- 不再把 `uploads/<input_key>` 作为 file 输入唯一解析方式

## Artifact Flow

### Current

`output.schema` -> prompt redirection -> fixed-path validation -> autofix move -> bundle allowlist

### New

`output.schema (x-type only)` -> terminal artifact resolve -> result rewrite -> contract-driven bundle

### Terminal resolve rules

1. 扫描 output schema 中所有 `x-type in {"artifact","file"}` 的字段
2. 从 output JSON 读取字段值
3. 解析为 run-local 实际文件
4. 若路径落在 run_dir 外，执行唯一兜底移动到 run 内安全位置
5. 将结果覆写为 bundle-relative path
6. required artifact 校验以“字段存在 + resolved 文件存在”为准

### Bundle rules

- 普通 bundle：
  - `result/result.json`
  - resolved artifact 文件
- debug bundle：
  - 保持 denylist 方式，继续打包宽范围运行产物

## Input File Flow

### New semantics

- 上传 zip 仍解压到 `run_dir/uploads/`
- file 类型输入在 `POST /v1/jobs` 的 `input.<key>` 中显式给出
- 该值是相对 `uploads/` 的安全相对路径
- 执行器在调用 CLI 前 resolve 为绝对路径并注入 `{{ input.<key> }}`

### Compatibility fallback

若请求体未给出某个 file key，则继续尝试旧规则：

- 查找 `run_dir/uploads/<input_key>`

该回退只作为兼容层，不再是主协议。

### E2E client alignment

- E2E run form submit MUST include file input paths in `input` together with inline values.
- E2E upload zip entries SHOULD preserve the uploaded filename under field folder:
  - `<field>/<original_filename>`
- This keeps E2E behavior aligned with the new declarative file-input protocol and avoids schema-key renaming debt.

## API changes

- `GET /v1/jobs/{request_id}/artifacts/{artifact_path}` 删除
- `GET /v1/jobs/{request_id}/artifacts` 保留，但返回 resolved artifact 相对路径列表
- `POST /v1/jobs` file 输入语义变更为显式相对路径引用

## Migration

- 旧 skill 可继续工作：
  - 旧 file strict-key 仍可回退
  - 旧 output 中写 `artifacts/...` 仍合法
- 新 skill 推荐：
  - 仅用 `x-type` 标记 artifact path
  - file 输入显式声明上传包内相对路径
