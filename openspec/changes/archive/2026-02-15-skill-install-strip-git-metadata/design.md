## Context

Skill 安装主流程在 `server/services/skill_package_manager.py` 中：

1. 解压到 `staging` 目录。
2. 校验 `runner.json`/`SKILL.md` 等结构。
3. 按 install/update 路径将目录移动到 `skills/<skill_id>/`。
4. 刷新 registry。

当前流程未处理上传包内可能存在的 `.git` 元数据。

## Goals

1. 在 install 与 update 场景下都移除 skill 包中的 `.git` 文件/目录。
2. 避免将 Git 元数据暴露到 `skills/<skill_id>/` 最终目录。
3. 保持现有安装协议与错误语义稳定。

## Non-Goals

1. 不改变 skill 包验证规则（不在 validator 阶段新增拒绝策略）。
2. 不清理与 Git 无关的隐藏文件（如 `.env`、`.github`、`.gitignore`）。
3. 不改动 RUN 执行流程与技能加载逻辑。

## Design

### 1) 清理时机

在 `staged_skill_dir` 完成结构校验后、进入 install/update 切换前执行清理：

- 优点：不会污染 live 目录；
- install/update 两条路径可复用同一清理逻辑；
- 出错时仍在 staging 范围内，便于回滚。

### 2) 清理范围

对 `staged_skill_dir` 递归扫描并删除命名为 `.git` 的节点：

- 若为目录：`shutil.rmtree(...)`
- 若为普通文件：`Path.unlink(...)`

默认清理全部层级中的 `.git` 节点（包含根级与嵌套目录）。

### 3) 错误处理

- 删除失败时抛出安装错误，安装请求标记为 failed；
- 保持与现有 install/update 错误路径一致，不新增特殊恢复逻辑；
- 在日志中记录被删除路径与失败原因，便于审计。

### 4) 测试策略

1. 单测：新安装包含 `.git/` 时，安装成功后 live 目录不含 `.git`。
2. 单测：更新安装包含 `.git` 文件时，更新成功后 live 目录不含 `.git`。
3. 回归：现有版本校验、归档与 registry 刷新测试保持通过。

## Risks & Mitigations

1. **风险：误删非目标文件**
   - 缓解：仅匹配名称精确为 `.git` 的文件/目录。
2. **风险：大包递归扫描带来额外开销**
   - 缓解：扫描范围仅限单个 `staged_skill_dir`，且发生在安装流程内一次性执行。
3. **风险：与后续路径移动操作耦合**
   - 缓解：清理逻辑封装为独立私有方法，避免散落在 install/update 分支。
