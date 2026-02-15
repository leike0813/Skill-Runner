## 1. 安装流程清理逻辑

- [x] 1.1 在 `skill_package_manager` 中新增私有方法：清理 `staged_skill_dir` 中的 `.git` 文件与目录
- [x] 1.2 在 `_process_install` 中于 staged 校验通过后调用清理方法（覆盖 install/update 两条路径）
- [x] 1.3 清理步骤补充必要日志（删除路径与异常信息）

## 2. 测试

- [x] 2.1 单测：上传包包含 `.git/` 目录，安装后 live skill 目录不包含 `.git`
- [x] 2.2 单测：更新包包含 `.git` 文件，更新后 live skill 目录不包含 `.git`
- [x] 2.3 回归现有 skill install 相关单测，确保版本升级/归档行为未回归

## 3. 文档

- [x] 3.1 更新 `docs/api_reference.md` 的 skill package 安装说明：安装会清理 `.git` 元数据
