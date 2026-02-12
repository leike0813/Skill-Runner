## ADDED Requirements

### Requirement: 目录原地改造是主入口
`skill-converter-agent` MUST 以“目标 skill 根目录”作为主输入入口，并在该目录中直接完成转换。

#### Scenario: 交互式调用目录模式
- **WHEN** 用户在 Agent 工具中指定一个 skill 根目录
- **THEN** Agent 在该目录内执行 `SKILL.md` 定义的改造流程（patch `SKILL.md`、生成 schema、生成 runner）
- **AND** 不要求用户先打 zip 包

### Requirement: zip 模式仅作为包装层
在 Skill-Runner 自动执行场景中，zip 输入 MUST 通过解包/打包包装实现，且转换逻辑与目录模式一致。

#### Scenario: zip 包装执行
- **WHEN** 输入为 zip 包
- **THEN** 系统先解包到固定目录
- **AND** 复用目录模式同一套转换逻辑
- **AND** 最后将结果重新打包为输出 artifact

### Requirement: 可转换性判定固定三类
转换判定 MUST 只使用以下三类：
- `not_convertible`
- `convertible_with_constraints`
- `ready_for_auto`

#### Scenario: 输出单一分类结果
- **WHEN** 完成源 skill 解析
- **THEN** 必须且仅返回一个分类

### Requirement: not_convertible 仅返回失败原因
当分类为 `not_convertible` 时，转换 MUST 终止，并且只返回失败原因。

#### Scenario: 不可转换场景中止
- **WHEN** 分类为 `not_convertible`
- **THEN** 不生成转换包
- **AND** 不输出成功类字段
- **AND** 只返回失败原因

### Requirement: SKILL.md 必须包含明确判定标准
`SKILL.md` MUST 明确描述“任务类型判断标准”和“可转换性判断标准”，并作为 Agent 决策依据。

#### Scenario: 判定标准可执行
- **WHEN** Agent 执行转换前分析
- **THEN** 能依据 SKILL.md 中定义的标准完成任务类型与可转换性判定

### Requirement: SKILL.md 必须提供 patch 提示与示例
`SKILL.md` MUST 提供可复用的 patch 提示策略，至少覆盖三类任务（直接返回、产出文件、修改文件），并附简短示例。

#### Scenario: Agent 依据模板执行 patch
- **WHEN** Agent 开始改造 `SKILL.md` 与 schema
- **THEN** 可直接使用模板化提示策略
- **AND** 输出符合 Skill-Runner 合同

### Requirement: 最终验证门必须保留
转换完成后 MUST 通过最终验证脚本校验产物契约。

#### Scenario: 转换后统一校验
- **WHEN** 转换文件生成完成
- **THEN** 执行验证脚本
- **AND** 校验失败则整体失败
