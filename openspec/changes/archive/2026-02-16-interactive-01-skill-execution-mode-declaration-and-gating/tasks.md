## 1. Skill 声明模型

- [x] 1.1 在 Skill manifest 模型中加入 `execution_modes`
- [x] 1.2 定义合法枚举：`auto|interactive`
- [x] 1.3 对缺失声明的存量 Skill 增加运行时兼容映射（`["auto"]` + deprecation 日志）

## 2. 包校验链路

- [x] 2.1 持久安装校验 `runner.json.execution_modes`（缺失/空/非法值拒绝）
- [x] 2.2 临时 skill 上传校验 `runner.json.execution_modes`（缺失/空/非法值拒绝）
- [x] 2.3 复用统一校验函数，避免重复实现

## 3. Job 提交准入

- [x] 3.1 在 `POST /v1/jobs` 校验请求模式是否被 Skill 声明允许
- [x] 3.2 在临时 skill run 提交链路校验请求模式是否被 Skill 声明允许
- [x] 3.3 拒绝时返回 400 + `SKILL_EXECUTION_MODE_UNSUPPORTED`

## 4. 测试

- [x] 4.1 单测：`execution_modes=["auto"]` 拒绝 interactive 请求
- [x] 4.2 单测：`execution_modes=["auto","interactive"]` 接受 interactive 请求
- [x] 4.3 单测：缺失 `execution_modes` 的新上传包被拒绝
- [x] 4.4 回归：存量缺失声明 Skill 仍可按 auto 执行（兼容期）

## 5. 文档

- [x] 5.1 更新 `docs/api_reference.md`：模式准入与错误码说明
- [x] 5.2 更新 `docs/dev_guide.md`：runner.json 新字段 `execution_modes` 规范
