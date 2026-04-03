## 1. OpenSpec

- [x] 1.1 创建 `claude-sandbox-policy-relaxation-and-fallback` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

## 2. Claude headless sandbox policy

- [x] 2.1 放宽 Claude headless enforced sandbox policy
- [x] 2.2 保持 dynamic run-local 限写并支持 sandbox list 配置叠加

## 3. Prompt and diagnostics

- [x] 3.1 为 Claude 默认 prompt 增加 sandbox fallback 使用约束
- [x] 3.2 将 Claude sandbox diagnostics 细化为 dependency / runtime / policy 三类

## 4. Validation

- [x] 4.1 更新 Claude config / prompt / parsing 回归测试
- [x] 4.2 运行目标 pytest
- [x] 4.3 运行目标 mypy
