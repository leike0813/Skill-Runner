## 1. 管理 API 分层

- [x] 1.1 新增 `management` 路由命名空间与版本化入口（`/v1/management/*`）
- [x] 1.2 定义 Skill / Engine / Run 三域统一 DTO（summary/detail）
- [x] 1.3 建立 Domain API 与 UI Adapter 的职责边界说明

## 2. Skill 管理 API

- [x] 2.1 提供技能列表统一接口（前端友好字段）
- [x] 2.2 提供技能详情统一接口（含 schemas/engines/files 摘要）
- [x] 2.3 对齐已安装健康状态/错误提示字段

## 3. Engine 管理 API

- [x] 3.1 提供引擎列表统一接口（版本、认证、沙箱状态）
- [x] 3.2 提供引擎详情统一接口（模型列表、升级状态）
- [x] 3.3 对齐升级结果与错误结构，避免 UI 私有解析

## 4. Run 管理 API（对话窗口）

- [x] 4.1 提供统一 run 状态接口（含 `pending_interaction_id` / `interaction_count`）
- [x] 4.2 提供统一文件树与文件预览接口
- [x] 4.3 接入并复用 `interactive-25` 的 SSE 流接口
- [x] 4.4 统一 pending/reply 管理动作接口（语义与 jobs 保持一致）
- [x] 4.5 统一 cancel 管理动作接口（语义与 `interactive-26` 保持一致）

## 5. 兼容与迁移

- [x] 5.1 保持现有 `/ui/*` 页面范围不变
- [x] 5.2 保持现有执行 API（`/v1/jobs*`, `/v1/temp-skill-runs*`）兼容
- [x] 5.3 为旧接口补充“推荐迁移到 management API”的文档注释

## 6. 测试与文档

- [x] 6.1 单测：管理 API DTO 字段稳定性
- [x] 6.2 单测：Run 对话窗口关键流程（state + events + pending/reply）
- [x] 6.3 集成：Skill/Engine/Run 管理接口端到端连通
- [x] 6.4 文档：`docs/api_reference.md` 新增 management API 章节
- [x] 6.5 文档：`docs/dev_guide.md` 增补 UI Adapter / Domain API 分层约定
