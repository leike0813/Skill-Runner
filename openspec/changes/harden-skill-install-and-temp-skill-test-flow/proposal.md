## Why

当前安装流程把“目录存在”直接视为“已安装 skill”，在以下场景会误判：

- submodule 未拉取导致目录存在但结构不完整；
- 人为拷贝/残留目录导致缺少 `assets/runner.json`。

误判后会进入更新分支并报 `Existing skill missing assets/runner.json`，导致无法重新安装。

同时，示例 skill 仅用于测试，不应作为部署技能的一部分长期驻留在 `skills/` 目录。

## What Changes

- 将“已安装判定”从“目录存在”收紧为“目录存在且安装结构有效（可读取有效版本）”。
- 对“目录存在但结构无效”的场景，自动迁移到 `skills/.invalid/` 后按 fresh install 处理。
- 调整测试框架，使 demo 场景通过临时 skill 上传运行：
  - suite 支持 `skill_source: temp` 与 `skill_fixture`；
  - integration 走内部服务编排（非 HTTP）；
  - e2e 走 `/v1/temp-skill-runs` API。
- 将 demo skill 迁移到 `tests/fixtures/skills/`，避免部署环境暴露。

## Impact

- 受影响服务：`SkillPackageManager`、`SkillRegistry`、`TempSkillRunManager`（测试调用路径）。
- 受影响测试框架：`tests/integration` 与 `tests/e2e` runner、suite 定义。
- 文档同步：测试规范与 API 文档中的安装行为说明。
