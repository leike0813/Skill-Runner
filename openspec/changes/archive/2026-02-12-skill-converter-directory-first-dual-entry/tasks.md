## 1. 目录优先流程重构

- [x] 1.1 重写 `skills/skill-converter-agent/SKILL.md`，明确“目录输入”为主流程（中文）
- [x] 1.2 在 `SKILL.md` 中补齐任务类型判断标准（直接返回 / 产出文件 / 修改文件）
- [x] 1.3 在 `SKILL.md` 中补齐可转换性判定标准（三分类）与判定依据输出要求
- [x] 1.4 明确 `not_convertible` 分支立即中止且仅返回失败原因

## 2. 双入口对齐（目录主入口 + zip 包装入口）

- [x] 2.1 调整参数契约，突出目录路径输入为主
- [x] 2.2 为 Skill-Runner 场景补充 zip 解包/打包包装脚本（不承载转换决策）
- [x] 2.3 在 runner 提示中说明 zip 仅包装，不引入独立转换逻辑

## 3. Patch 指令与示例增强

- [x] 3.1 在 `SKILL.md` 中加入 patch 提示词策略（按任务类型区分）
- [x] 3.2 增加简短示例：如何 patch `SKILL.md`
- [x] 3.3 增加简短示例：如何生成 `input/parameter/output schema` 与 `runner.json`

## 4. 验证门与契约

- [x] 4.1 保留最终验证脚本入口，确保转换完成后统一校验
- [x] 4.2 保证目录模式和 zip 模式都走同一校验门
- [x] 4.3 补充 `not_convertible` 输出约束测试

## 5. 测试

- [x] 5.1 新增/更新单测：目录主入口转换流程
- [x] 5.2 新增/更新单测：zip 包装入口复用目录逻辑
- [x] 5.3 新增/更新单测：三分类判定输出语义
- [x] 5.4 跑 `mypy` 与目标 pytest 集合

## 6. 文档同步

- [x] 6.1 更新 `skills/skill-converter-agent/SKILL.md`（中文完整版）
- [x] 6.2 同步更新相关 docs（若涉及调用方式变化，当前无额外 docs 受影响）
- [x] 6.3 更新本 change 勾选状态并通过 OpenSpec 校验
