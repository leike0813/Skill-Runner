# configurable-on-demand-engine-bootstrap Proposal

## Summary

将 engine 安装从“部署时默认全量 ensure”改为“可配置的子集 ensure”，默认仅预装 `opencode,codex`。其余 engine 不再在 bootstrap/install 阶段被隐式安装，而是由调用方显式再次执行 `bootstrap/install --engines ...`。

同时，管理 UI 的 engine 管理页复用现有单 engine 升级按钮承载安装能力：未安装时显示“安装”，已安装时显示“升级”。

## Motivation

当前 bootstrap/install 总是全量安装所有受管 engine，带来：

- 本地部署耗时长，且对用户当前不使用的 engine 做了不必要安装
- 插件和本地链路无法控制安装范围
- 管理 UI 只能升级已安装 engine，无法对缺失 engine 做显式安装

本次 change 的目标是把安装行为收敛到“明确的目标集合”，并让本地控制链路与 UI 都能显式安装指定 engine。

## Scope

- 扩展 `agent_manager.py --ensure` 支持 `--engines <csv|all|none>`
- 扩展 `skill-runnerctl bootstrap/install` 支持 `--engines <csv|all|none>`
- 新增环境变量 `SKILL_RUNNER_BOOTSTRAP_ENGINES`
- 调整 release installer 与 container entrypoint 的默认 bootstrap 集合为 `opencode,codex`
- 扩展 engine upgrade 任务域，让单 engine 动作可根据安装状态执行 install 或 upgrade
- 管理 UI 复用单 engine 升级按钮承载安装能力

## Non-Goals

- 不做运行中的隐式自动补装
- 不新增单独的 install-engine CLI 或 management API
- 不改变 jobs/run 在 CLI 缺失时的失败语义
- 不修改 “Upgrade All” 的用户入口形态
