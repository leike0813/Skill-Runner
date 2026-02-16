## 1. 客户端 API 迁移

- [ ] 1.1 梳理内建 Web 客户端对旧 UI 数据接口的依赖清单
- [ ] 1.2 新增/整理统一 management API client 层
- [ ] 1.3 Skill 页面改为管理 API 数据源
- [ ] 1.4 Engine 页面改为管理 API 数据源
- [ ] 1.5 Run 页面改为管理 API 数据源

## 2. Run 对话窗口改造

- [ ] 2.1 接入 Run 状态与交互态字段（`pending_interaction_id`, `interaction_count`）
- [ ] 2.2 接入 SSE 实时输出流并处理重连
- [ ] 2.3 接入 pending/reply 动作并联动状态刷新
- [ ] 2.4 保留文件树与文件预览能力，并对齐新 DTO 字段
- [ ] 2.5 接入 cancel 动作并处理取消后 UI 状态收敛

## 3. 旧接口弃用

- [ ] 3.1 为旧 UI 数据接口标记 deprecated 并补充替代路径
- [ ] 3.2 增加旧接口调用观测（日志/指标）
- [ ] 3.3 验证内建 Web 客户端不再依赖旧接口
- [ ] 3.4 定义并实现 removal 策略（410 或移除）及版本窗口说明

## 4. 测试

- [ ] 4.1 单测：管理 API DTO 到 UI 渲染字段映射
- [ ] 4.2 单测：Run 对话窗口三态（running/waiting_user/terminal）
- [ ] 4.3 单测：SSE 断线重连与增量续传
- [ ] 4.4 集成：Skill/Engine/Run 页面在新接口下完整可用
- [ ] 4.5 回归：旧接口弃用后不影响核心执行链路
- [ ] 4.6 单测：Run 页面 cancel 后状态与交互控件正确切换

## 5. 文档

- [ ] 5.1 更新 `docs/api_reference.md`：新增“管理 API 为前端首选”的说明
- [ ] 5.2 更新 `docs/dev_guide.md`：记录 UI Adapter 与 management API 的分层约定
- [ ] 5.3 增加旧接口弃用与移除时间线说明
