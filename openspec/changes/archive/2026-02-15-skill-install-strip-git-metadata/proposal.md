## Why

当前 skill package 安装流程会把上传包内容直接落到 `skills/<skill_id>/`。  
如果上传包中包含 `.git` 文件或 `.git/` 目录，可能与父仓库/子模块管理产生冲突，带来以下风险：

1. 在主项目下出现意外 Git 元数据，影响开发者本地仓库行为。
2. 某些工具将 skill 目录误识别为独立仓库，导致路径解析/扫描行为异常。
3. 更新安装时遗留 `.git` 元数据可能跨版本持续存在，难以定位来源。

因此需要在安装完成前对已验证的 skill 内容执行一次 Git 元数据清理。

## What Changes

1. 在 skill install / update 流程中增加“Git 元数据清理”步骤。
2. 清理目标至少包括：
   - `.git` 目录
   - `.git` 普通文件
3. 该清理逻辑仅作用于已通过验证、即将落地到 `skills/<skill_id>/` 的安装内容。
4. 清理后不改变既有安装协议（版本校验、归档、注册刷新等行为保持不变）。

## Impact

- `server/services/skill_package_manager.py`
- `tests/unit/test_skill_package_manager.py`
- `tests/integration/test_skill_package_install_api.py`（如需补充端到端断言）
- `docs/api_reference.md`（安装行为说明）
