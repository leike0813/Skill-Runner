## Context

管理端已有系统设置与数据重置接口，但缺少日志检索 API。  
日志来源当前分为：
- 应用日志族：`skill_runner.log*`（配置目录由 `config.SYSTEM.LOGGING.DIR` + `FILE_BASENAME` 决定）
- 容器 bootstrap 日志族：`bootstrap.log*`（位于 `data/logs`）

## Goals / Non-Goals

**Goals**
- 提供单接口查询系统日志与 bootstrap 日志。
- 支持关键词/级别/时间范围筛选与 cursor 分页。
- System Console 页面直接消费该接口，不改变现有设置与重置链路。

**Non-Goals**
- 不新增日志写入后端、SSE 推送或索引存储。
- 不改日志协议与业务事件模型。
- 不支持任意路径日志读取。

## Decisions

### 1) Source 白名单硬限制

- `source=system` 仅允许读取 `skill_runner.log*`
- `source=bootstrap` 仅允许读取 `bootstrap.log*`
- 不接受外部传入文件路径

### 2) 查询策略

- 读取日志文件族后聚合成行记录，按时间倒序（新到旧）
- 分页基于稳定 offset cursor（从 0 开始）
- `limit` 默认 200，最大 1000

### 3) 解析与降级

- JSON 行：解析 `timestamp/level/message`
- 文本行：尝试解析 `YYYY-mm-dd HH:MM:SS LEVEL logger: message`
- bootstrap 行：尝试解析 `ts=...` 与 `level=...`
- 解析失败仍保留 `raw` 并参与关键词匹配（best-effort）

### 4) UI 集成

- `/ui/settings` 路由保持不变；标题与导航文案改为 System Console
- 新增 Log Explorer 卡片与独立 JS 逻辑，和 Logging/Reset 模块并存
- 使用 cursor 的 `Load more` 拉取历史记录

## Risks / Trade-offs

- [Risk] 纯文件扫描在超大日志场景性能受限  
  → Mitigation: 限制源范围 + 默认 limit + 页面按需加载。

- [Risk] 不同日志格式时间解析不一致  
  → Mitigation: 时间过滤采用 best-effort；无法解析时间的行在启用时间过滤时剔除。

## Migration Plan

1. 先新增后端查询服务与路由。
2. 再接入 settings 页面 Log Explorer UI。
3. 更新 i18n 与文档。
4. 补单测并验证。
