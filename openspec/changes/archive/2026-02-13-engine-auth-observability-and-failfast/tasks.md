## 1. 鉴权可观测性（API/UI/脚本）

- [x] 1.1 在 `AgentCliManager` 增加 auth 状态聚合（managed/global 路径来源 + 凭证明细）
- [x] 1.1.1 在 `AgentCliManager` 固化 iFlow managed 默认 settings 基线（`oauth-iflow` + `baseUrl`）并实现 legacy 自动迁移
- [x] 1.2 新增 `GET /v1/engines/auth-status` 接口与响应模型
- [x] 1.3 在 `/ui/engines` 页面增加鉴权状态显示与路径来源提示
- [x] 1.4 新增 `scripts/check_agent_auth.sh` 与 `scripts/check_agent_auth.ps1`

## 2. managed 判定修复

- [x] 2.1 修复 `ensure` 判定：仅 `managed_present` 视为已安装
- [x] 2.2 保留 `global_available` 仅用于诊断，不参与安装决策
- [x] 2.3 补充单元测试覆盖 iflow 跑偏场景

## 3. 执行 fail-fast

- [x] 3.1 在 adapter 基类增加硬超时（默认 600s，环境变量可覆盖）
- [x] 3.2 超时后终止子进程并保留输出日志
- [x] 3.3 基于输出做 AUTH_REQUIRED/TIMEOUT 归类
- [x] 3.4 将归类结果标准化写入 run 终态错误信息

## 4. 测试与文档

- [x] 4.1 增加 auth 状态接口/UI 的单元测试
- [x] 4.1.1 增加 iFlow legacy settings -> baseline 自动迁移测试
- [x] 4.2 增加 fail-fast 与错误归类测试
- [x] 4.3 更新 `README.md` / `README_CN.md` / `docs/api_reference.md`
- [x] 4.4 运行类型检查与全量单元测试
