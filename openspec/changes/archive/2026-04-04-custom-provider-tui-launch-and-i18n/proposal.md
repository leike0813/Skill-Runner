# custom-provider-tui-launch-and-i18n Proposal

## Summary

在引擎管理页的 custom provider 区新增 provider-row 级“启动 TUI”能力，并补齐 custom provider 相关多语言文案。

## Motivation

当前 custom provider 管理页只支持 CRUD，用户保存 provider 后仍需要回到其他入口手工选择模型并启动会话，链路不连贯。同时 custom provider 区大量依赖模板内联默认文案，缺少正式 locale key。

## Scope

- 在 custom provider 表格操作列新增 provider-row 级“启动 TUI”
- TUI 启动接口支持可选 `custom_model=provider/model`
- Claude UI shell 会话支持把 `provider/model` 注入 session-local `.claude/settings.json`
- 为 custom provider 功能补齐 locale key

## Non-Goals

- 不做跨 engine 的 provider 共享
- 不新增 management CRUD API
- 不要求其他 engine 立即支持 provider-backed TUI

## Capabilities

### Modified Capabilities

- `ui-engine-management`
- `engine-adapter-runtime-contract`

