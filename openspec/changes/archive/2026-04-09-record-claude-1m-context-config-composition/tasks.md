## 1. Claude Runtime Override

- [x] 1.1 将 Claude 模型 override helper 提升为返回完整 runtime override 结构
- [x] 1.2 为官方 `[1m]` 模型写入 `CLAUDE_CODE_DISABLE_1M_CONTEXT="0"`
- [x] 1.3 为 custom provider `[1m]` 模型写入根 `model="sonnet[1m]"` 与 `ANTHROPIC_DEFAULT_SONNET_MODEL`
- [x] 1.4 在 custom provider `[1m]` 的最终配置中移除 `ANTHROPIC_MODEL`

## 2. Shared Consumers

- [x] 2.1 让 Claude UI shell session config 复用同一套 runtime override 构造逻辑
- [x] 2.2 让 Claude custom provider 解析接受带 `[1m]` 后缀的模型规格
- [x] 2.3 对齐 Claude 默认配置中 1M 开关的字符串值类型

## 3. Verification

- [x] 3.1 更新 Claude config composer 回归测试，覆盖官方与 custom provider 的 `[1m]` 路径
- [x] 3.2 更新 Claude UI shell 回归测试，覆盖 custom provider `[1m]` 路径
- [x] 3.3 运行定向 pytest 与 mypy 验证
