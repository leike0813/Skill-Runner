# contract-driven-artifact-resolution-and-declarative-input-file-paths

## Why

当前文件协议存在两类过度耦合：

1. artifact 依赖 prompt 注入把产物强制重定向到 `artifacts/`，并要求 validator 以固定目录/固定命名校验，导致：
   - agent 不遵守 prompt 时需要额外 autofix
   - 动态文件名与 required artifact 冲突
   - bundle/下载/文档都绑定 `artifacts/` 命名空间
2. file 输入要求上传包内文件名必须等于 input key，导致上传包组织形式过于死板，扩展名和嵌套目录难以保留。

## What Changes

- artifact 协议改为 contract-driven：
  - `x-type: artifact|file` 保留
  - `x-filename` 废弃
  - 终态统一 resolve output 中的 artifact path，并覆写 `result.json`
  - 普通 bundle 仅打包 `result/result.json` 与 resolved artifact 文件
  - 删除 artifact 单文件下载接口
- 输入文件协议改为声明式：
  - `POST /v1/jobs` 中 file 类型输入也显式通过 `input` 提交
  - 值为 `uploads/` 根下相对路径
  - 上传 zip 允许任意目录组织
  - 执行前统一 resolve 为绝对路径注入 prompt
  - 旧的 `uploads/<input_key>` strict-key 匹配保留为兼容回退
- 内建 E2E 示例客户端同步切换到新提交语义：
  - 创建 run 时将 file 类型输入路径一并写入 `input`
  - 上传 zip 条目采用 `<field>/<original_filename>`，不再按字段名重命名

## Impact

- 影响 `jobs` API 的 file 输入语义与 artifact 下载能力
- 影响 bundle 构建、终态 validator、skill patcher、schema 文档与测试
- debug bundle 语义保持不变，继续承担完整排障包职责
