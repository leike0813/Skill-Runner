## 1. 决策协议

- [x] 1.1 定义交互 `kind` 枚举与 Agent 提问载荷字段
- [x] 1.2 在 interaction 载荷中加入 `prompt/options/ui_hints` 与 `default_decision_policy`
- [x] 1.3 校验 pending 提问载荷完整性，并允许 reply 自由文本
- [x] 1.4 补充 interactive 模式 Skill patch 提示词模板（仅约束 Agent 提问格式）
- [x] 1.5 确认 auto 模式仍使用自动执行提示词模板，不注入交互提问约束

## 2. strict 开关

- [x] 2.1 新增 `interactive_require_user_reply` 选项（默认 `true`）
- [x] 2.2 在 options_policy 中新增校验与默认值注入
- [x] 2.3 文档化 strict on/off 行为矩阵

## 3. 编排行为（按档位）

- [x] 3.1 `resumable + strict=true`：保持 waiting_user，不自动推进
- [x] 3.2 `sticky_process + strict=true`：超时失败（`INTERACTION_WAIT_TIMEOUT`）
- [x] 3.3 `resumable + strict=false`：超时后自动回复并 resume 继续
- [x] 3.4 `sticky_process + strict=false`：超时后自动注入并继续执行

## 4. 审计与可观测

- [x] 4.1 交互历史记录 `resolution_mode`（user/auto）
- [x] 4.2 记录自动决策触发时间与原因
- [x] 4.3 状态接口补充自动决策统计字段（如 `auto_decision_count`）

## 5. 测试

- [x] 5.1 单测：各 `kind` 下 reply 自由文本均可被接受
- [x] 5.2 单测：strict=true 下 resumable 不自动推进
- [x] 5.3 单测：strict=true 下 sticky_process 超时失败
- [x] 5.4 单测：strict=false 下 resumable 自动决策后 resume
- [x] 5.5 单测：strict=false 下 sticky_process 自动注入后继续
- [x] 5.6 集成：用户无回复场景的两档位行为矩阵
- [x] 5.7 单测：interactive 模式 patch 包含 `kind/prompt` 等提问载荷约束
- [x] 5.8 单测：auto 模式 patch 不包含交互提问约束，但保留自动执行约束

## 6. 文档

- [x] 6.1 更新 `docs/api_reference.md`：决策协议与 strict 开关说明
- [x] 6.2 更新 `docs/dev_guide.md`：自动决策审计字段与运维建议
