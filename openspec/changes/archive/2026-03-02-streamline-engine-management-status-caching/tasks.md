## 1. OpenSpec artifacts

- [x] 1.1 创建 `streamline-engine-management-status-caching` change
- [x] 1.2 补齐 proposal / design / tasks
- [x] 1.3 编写 delta specs：`management-api-surface`、`web-management-ui`、`ui-engine-inline-terminal`
- [x] 1.4 编写新 capability spec：`engine-status-cache-management`

## 2. Engine version cache service

- [x] 2.1 新增 `server/services/engine_management/engine_status_cache_service.py`
- [x] 2.2 复用 `AgentCliManager` 版本探测逻辑并提供单引擎刷新入口
- [x] 2.3 在服务中实现 startup refresh 与每日后台刷新

## 3. Read path and upgrade integration

- [x] 3.1 `model_registry` 改为只读缓存版本，不再在读路径现场探测
- [x] 3.2 `engine_upgrade_manager` 在升级成功后刷新对应 engine 版本缓存
- [x] 3.3 `server/main.py` 接入 startup refresh 和 scheduler 生命周期

## 4. API and UI simplification

- [x] 4.1 `management.py` 删除 auth/sandbox 摘要字段和探测逻辑
- [x] 4.2 `server/models/management.py` 收缩 engine summary/detail 模型
- [x] 4.3 `server/routers/engines.py` 删除 `/v1/engines/auth-status`
- [x] 4.4 `/ui/engines` 改为 SSR 直接渲染表格
- [x] 4.5 engine 表格 partial 删除 `Auth Ready` 和 `Sandbox` 列

## 5. Verification

- [x] 5.1 更新单元测试与集成测试
- [x] 5.2 更新文档
- [x] 5.3 运行指定 pytest 集合
- [x] 5.4 运行 mypy
