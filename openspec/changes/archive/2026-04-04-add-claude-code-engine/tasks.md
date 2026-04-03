## 1. OpenSpec

- [x] 1.1 创建 `add-claude-code-engine` change 工件
- [x] 1.2 补齐 proposal / design / delta specs

## 2. Claude engine package

- [x] 2.1 新增 `server/engines/claude/**` adapter/config/models/auth 目录
- [x] 2.2 实现 Claude execution adapter / command builder / config composer / stream parser
- [x] 2.3 新增 Claude adapter profile / command profile / auth strategy / settings schema / model manifest

## 3. Central wiring

- [x] 3.1 将 `claude` 加入 engine keys 与集中注册点
- [x] 3.2 接入 managed install / upgrade / status / model registry / bootstrap
- [x] 3.3 将 `claude` 纳入 CTL / preflight / doctor / UI engine management

## 4. Auth and UI

- [x] 4.1 实现 Claude `oauth_proxy` 与 `cli_delegate`
- [x] 4.2 管理 UI engine auth 热点改为 metadata-driven
- [x] 4.3 E2E 示例客户端支持 `claude`

## 5. Validation

- [x] 5.1 补齐 Claude 与集中注册回归测试
- [x] 5.2 运行目标 pytest
- [x] 5.3 运行目标 mypy
