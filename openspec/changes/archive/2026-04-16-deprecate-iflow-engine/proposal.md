## Why

`iflow` 已不再作为项目的活跃引擎能力维护，但当前仍然挂在引擎注册、UI、模型目录、鉴权链路、schema 合同和测试真源中。继续保留这些接线会让新 run、管理页、e2e 表单和 skill manifest 继续把 `iflow` 暴露成可选引擎，也会让当前公共合同与实际支持面不一致。

本 change 需要把 `iflow` 正式降级为仓库内封存代码：代码保留原位，所有活跃入口断开，同时保留历史 run 的只读兼容。

## What Changes

- 从当前支持引擎真源中移除 `iflow`，包括引擎注册、auth bootstrap、detector registry、UI、e2e、engine upgrade、model registry 和 skill engine policy。
- 从 active schema/contract 中移除 `iflow` 枚举与相关活跃约束。
- 保留 `server/engines/iflow/` 原位不动，但不再被任何活跃 registry/import chain 引用。
- 为历史 `.iflow` run 目录保留只读兼容，不影响旧 run 文件浏览、审计详情与事件查看。
- 将活跃测试从“支持 iflow”切换为“iflow 已废弃”，并把 iflow 专属测试移出默认活跃回归面。
