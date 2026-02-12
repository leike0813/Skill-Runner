## 背景

Skill-Runner 已有如下后端能力：

- `GET /v1/skills`、`GET /v1/skills/{skill_id}`：技能查询
- `POST /v1/skill-packages/install`、`GET /v1/skill-packages/{request_id}`：异步安装

因此 Web 管理界面不需要重做业务核心，只需补齐“可视化入口 + 安全控制”。

## 目标

1. 提供 `/ui` 管理入口，展示技能列表与用途
2. 提供网页上传 Skill 包并安装的交互流程
3. 提供安装状态轮询与结果回显
4. 增加基础鉴权，并支持容器环境变量配置

## 技术选型

- 后端：FastAPI（现有）
- 模板：Jinja2（现有依赖）
- 交互：HTMX（轻量增量交互）
- 不引入 Node/TypeScript 构建链，保持 Python-first

## 路由设计

### UI 路由

- `GET /ui`
  - 返回管理首页模板
  - 页面包含两个区域：技能列表、技能包安装

- `GET /ui/skills/table`
  - 返回技能表格 partial（供 HTMX 局部刷新）
  - 列信息：`id`、`name`、`description`、`version`、`engines`

- `POST /ui/skill-packages/install`
  - 接收网页文件上传
  - 复用现有安装流程，返回 request_id 和初始状态（partial/json）

- `GET /ui/skill-packages/{request_id}/status`
  - 轮询安装状态（供 HTMX 定时刷新）
  - 终态时回显成功/失败信息

> 注：后端实现上可调用同一套 service/store，不重复实现安装逻辑。

## 鉴权设计

### 范围

- 鉴权开启后，至少保护：
  - `/ui` 及其子路由
  - `/v1/skill-packages/*`（避免绕过 UI 直接上传）

### 方式

- 使用 HTTP Basic Auth
- 配置项（支持环境变量覆盖）：
  - `UI_BASIC_AUTH_ENABLED`：`true/false`，默认 `false`
  - `UI_BASIC_AUTH_USERNAME`
  - `UI_BASIC_AUTH_PASSWORD`

### 启动行为

- 当 `UI_BASIC_AUTH_ENABLED=true` 且用户名/密码缺失时：
  - 启动失败（fail fast），防止“误以为已开启保护”

## 容器化配置

在 `docker-compose.yml` 示例中增加：

- `UI_BASIC_AUTH_ENABLED=true`
- `UI_BASIC_AUTH_USERNAME=<your-user>`
- `UI_BASIC_AUTH_PASSWORD=<your-password>`

并在文档中说明：

- 生产环境建议通过 `.env` 或 secrets 注入
- 不要把明文密码提交到仓库

## 错误处理与交互细节

- 上传空文件：页面显示可读错误
- 上传非法包：展示后端校验错误
- 安装失败：显示失败原因（status + error）
- 安装成功：自动刷新技能列表并高亮新安装 skill

## 测试策略

1. 单元测试
   - `/ui` 路由返回
   - 鉴权开关逻辑
   - 安装轮询终态逻辑

2. 集成测试
   - 从 UI 上传到安装成功的完整链路
   - 开启鉴权后的 401/200 分支

## 风险与缓解

- 风险：UI 与 `/v1` 安装能力行为漂移  
  缓解：UI 直接复用同一 service，不复制业务逻辑。

- 风险：鉴权误配置导致管理口裸露  
  缓解：提供 `ENABLED=true` 但凭据缺失时 fail fast。
