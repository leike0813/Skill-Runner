## MODIFIED Requirements

### Requirement: 运行时补丁 MUST 与执行模式一致
系统 MUST 基于 execution_mode 生成一致的运行时指令补丁，并将补丁分为两层：  
1) 模式无关补丁（artifact 重定向与 completion contract 注入）  
2) 模式相关补丁（auto/interactive 的交互语义约束）
并且 completion contract 注入文案 MUST 来自可版本化的 Markdown 配置文件，不得在代码中硬编码文本正文。

#### Scenario: auto 模式补丁
- **WHEN** run 以 `auto` 模式执行
- **THEN** 补丁保持“不得询问用户决策”的约束
- **AND** 补丁要求任务完成时输出 completion marker（仅允许 `__SKILL_DONE__` 大写字段）

#### Scenario: interactive 模式补丁
- **WHEN** run 以 `interactive` 模式执行
- **THEN** 补丁允许请求用户输入
- **AND** 补丁要求输出结构化 ask_user 载荷
- **AND** 未完成前不得提前输出 completion marker

#### Scenario: artifact 重定向补丁在两种模式都生效
- **WHEN** run 以 `auto` 或 `interactive` 模式执行
- **THEN** 都会注入 artifact 输出重定向补丁
- **AND** 输出路径被约束到 run 的 `artifacts/` 目录

#### Scenario: completion contract 注入幂等
- **WHEN** 同一 skill 在同一运行上下文被重复 patch
- **THEN** completion contract 只注入一次
- **AND** 不产生重复段落或冲突规则

#### Scenario: 注入文案来自 Markdown 配置
- **WHEN** 系统执行 completion contract 注入
- **THEN** 文案内容从约定的 Markdown 配置文件读取
- **AND** 注入逻辑不包含内联硬编码正文

#### Scenario: 配置文件缺失时失败并告警
- **WHEN** completion contract Markdown 配置文件不存在或不可读
- **THEN** 系统以明确错误终止注入流程
- **AND** 运行状态与日志中包含可定位的配置错误信息

#### Scenario: JSON 最终输出携带 done marker
- **WHEN** skill 最终输出为 JSON 对象
- **THEN** done marker 以内嵌字段方式输出（`"__SKILL_DONE__": true`）
- **AND** 不需要额外单独 done 对象

#### Scenario: 非 JSON 最终输出补充 done marker
- **WHEN** skill 最终输出不是 JSON 对象
- **THEN** 系统要求输出单独 done 对象
- **AND** done 对象输出后不得追加额外内容

#### Scenario: 单轮出现多个 done marker
- **WHEN** 同一回合输出中出现多个 `__SKILL_DONE__` 标记
- **THEN** 系统按首个 marker 判定为发现完成标记
- **AND** 后续 marker 被忽略并记录诊断告警

## ADDED Requirements

### Requirement: 引擎解析结果 MUST 与完成态判定协同
系统 MUST 将 turn 协议解析结果与 completion marker/终止信号协同使用，以判定 `completed/awaiting_user_input/interrupted/unknown`。

#### Scenario: ask_user 回合进入等待态
- **WHEN** turn 协议解析为 `outcome=ask_user` 且载荷合法
- **THEN** run 进入 `waiting_user`
- **AND** 不判定为 `completed`

#### Scenario: final 回合缺失 done marker
- **WHEN** turn 协议解析为 `outcome=final` 且命中终止信号但缺失 done marker
- **THEN** 系统判定为 `awaiting_user_input` 或输出诊断告警
- **AND** 不将该回合静默判定为成功完成

#### Scenario: done marker 与进程失败同时出现
- **WHEN** 回合输出命中 `__SKILL_DONE__` 但进程以非零退出码或中断信号结束
- **THEN** 系统优先判定该回合为 `interrupted`
- **AND** 在诊断信息中记录完成标记与进程失败冲突
