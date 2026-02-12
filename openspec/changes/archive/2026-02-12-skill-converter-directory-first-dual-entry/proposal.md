## 为什么要做

当前 `skill-converter-agent` 的定位仍偏向“为 Skill-Runner 自动执行而设计”。  
你现在明确的新目标是：

1. 首先把它作为一个普通 Agent Skill 来用：用户在 Codex/Gemini CLI 里通过 Prompt 调用，并指定一个**现有 Skill 根目录**，Agent 直接在该目录内改造。
2. Skill-Runner 自动执行模式只是“包装层”：接收 zip -> 解包到固定目录 -> 复用同一套目录改造逻辑 -> 重新打包输出。

因此需要把能力模型重构为“目录优先，zip 仅包装”。

## 变更内容

- 新增目录优先执行规范：以 `source_skill_path` 作为主入口，直接原地改造目标 skill。
- 新增 zip 包装执行规范：仅负责解包/回收，不引入独立转换逻辑。
- 扩写 `SKILL.md` 指令体系（中文）：
  - 任务类型判断方法
  - 可转换性判定标准
  - patch 提示词策略与示例
  - 非可转换场景的中止规则
- 保持最终验证脚本机制：目录改造后由验证脚本统一检查契约。

## 能力影响

### 新增能力

- `skill-converter-directory-first`：目录原地改造能力（交互式优先）。
- `skill-converter-zip-wrapper`：Skill-Runner 包装执行能力（解包/打包）。

### 修改能力

- `skill-converter-agent` 从“zip 输入驱动”调整为“目录输入驱动，zip 仅包装”。

## 影响范围

- `skills/skill-converter-agent/SKILL.md`（核心重写，中文扩展）
- `skills/skill-converter-agent/assets/parameter.schema.json`（入口参数收敛）
- `skills/skill-converter-agent/assets/runner.json`（包装执行流程说明）
- `skills/skill-converter-agent/scripts/`（保留验证脚本，新增/复用解包打包包装脚本）
- 对应单元测试与集成测试
