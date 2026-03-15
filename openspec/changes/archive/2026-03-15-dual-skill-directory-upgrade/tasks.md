## 1. Registry and Install Semantics

- [x] 1.1 将 skill 注册扫描改为双目录顺序：`skills_builtin` -> `skills`，并实现同 ID 用户覆盖。
- [x] 1.2 将 skill 包安装/更新/归档/invalid-staging 全部限定到用户目录 `skills/`。
- [x] 1.3 校验内建目录只读语义：安装链路不得写入或覆盖 `skills_builtin/`。

## 2. Management API and UI

- [x] 2.1 在 Skill 管理摘要/详情数据模型中增加 `is_builtin` 字段并从最终生效来源计算。
- [x] 2.2 管理 UI 首页与 `/ui/management/skills/table` 按 `is_builtin` 渲染内建标识。
- [x] 2.3 增加“同 ID 用户覆盖”场景回归，确保标识在覆盖时消失。

## 3. Packaging and Deployment Artifacts

- [x] 3.1 更新镜像构建与发布链路：内建 skill 来源改为 `skills_builtin/`。
- [x] 3.2 更新 `docker-compose` 模板为用户目录 `skills/` 的 bind mount 语义。
- [x] 3.3 同步 README 与容器化文档，明确双目录与覆盖规则。

## 4. Verification

- [x] 4.1 增加/更新 registry 层测试：仅内建、仅用户、同 ID 覆盖三种场景。
- [x] 4.2 增加/更新 management API 测试：`is_builtin` 返回语义正确。
- [x] 4.3 增加/更新 UI 测试：内建标识显示与覆盖消失行为正确。
