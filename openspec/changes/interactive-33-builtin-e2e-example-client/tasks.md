## 1. 管理 API schema 能力扩展

- [x] 1.1 在 `server/models.py` 增加 Skill schema 响应模型（input/parameter/output）
- [x] 1.2 在 `server/routers/management.py` 新增 Skill schema 查询接口（按 skill_id 返回 schema 内容）
- [x] 1.3 为 schema 查询接口补充错误语义（不存在 skill 返回 404，响应不泄露内部路径）

## 2. 示例客户端独立服务搭建

- [x] 2.1 在 `e2e_client/` 新增示例客户端独立 app 入口与配置模块（不放在 `server/`）
- [x] 2.2 实现端口策略：默认 `8011`，支持 `SKILL_RUNNER_E2E_CLIENT_PORT` 覆盖，异常值回退 `8011`
- [x] 2.3 新增示例客户端路由与模板目录结构（沿用 Jinja2 + htmx + 原生 JS 技术栈）
- [x] 2.4 新增客户端首页：通过 management API 读取并展示 Skill 列表与描述

## 3. 执行与交互流程实现

- [x] 3.1 新增执行页：按 schema 动态渲染 inline input / parameter / file 上传控件
- [x] 3.2 实现提交前校验与请求打包，调用 `/v1/jobs` 与上传接口
- [x] 3.3 新增运行页：消费状态与 SSE 事件流展示 stdout/stderr
- [x] 3.4 实现 waiting_user 下 pending/reply 交互，直至终态收敛
- [x] 3.5 保持低耦合边界：客户端仅通过 HTTP API 交互，不直接依赖 `server` 内部服务实现
- [x] 3.6 实现录制能力：对创建/上传/pending/reply/结果读取写入结构化会话文件
- [x] 3.7 实现单步回放视图：按步骤展示已录制会话中的关键交互结果

## 4. 结果展示、文档与测试

- [x] 4.1 新增结果页：读取并展示 result 与 artifacts（含下载入口）
- [x] 4.2 更新 `docs/api_reference.md` 与 `docs/dev_guide.md` 中示例客户端服务与调用流程说明
- [x] 4.3 新增 `docs/e2e_example_client_ui_reference.md`，沉淀 UI 信息架构、页面布局与状态规范
- [x] 4.4 增加集成测试覆盖示例客户端关键流程（初始化、执行、交互、结果展示、录制回放）

## 5. 可重入观测与结果页交互一致性增强

- [x] 5.1 新增客户端 Runs 入口页，列出已创建 run 并提供 `Open Observation` 重入按钮
- [x] 5.2 调整导航与页面入口：Replay 作为 run 观测页子功能保留，不再作为唯一重入入口
- [x] 5.3 将结果页 bundle 文件树与预览改造成与内建管理 UI run 观测页同构交互（树+预览+局部加载）
- [x] 5.4 补充集成测试覆盖上述增强行为（runs 重入、结果页预览局部加载）
