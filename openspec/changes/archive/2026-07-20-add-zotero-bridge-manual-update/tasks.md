## 1. Managed bundle 状态与更新服务

- [x] 1.1 从实际生效 manifest 投影版本、来源和 active commit
- [x] 1.2 将 updater 拆分为只查询与安装已确认候选的共享原语
- [x] 1.3 保持后台自动更新、失败 fallback、并发互斥和幂等语义

## 2. Management API

- [x] 2.1 新增插件状态响应 DTO 并从 models 包导出
- [x] 2.2 新增本地状态、检查更新和安装更新接口
- [x] 2.3 为所有插件管理接口增加 UI Basic Auth 保护及冲突错误映射

## 3. System Console UI

- [x] 3.1 在日志设置上方增加插件状态 partial
- [x] 3.2 实现两阶段检查/安装交互、忙碌态和可访问状态反馈
- [x] 3.3 同步 zh/en/fr/ja 文案

## 4. Tests and documentation

- [x] 4.1 扩展 bundle/updater 单测覆盖版本来源、查询、安装、漂移、幂等与失败回退
- [x] 4.2 扩展 management/UI/i18n 单测覆盖合同、鉴权和页面结构
- [x] 4.3 同步 managed plugin、API reference 与 Zotero 集成文档
- [x] 4.4 运行相关最小测试与 OpenSpec 校验

## 5. Bundle 合同治理

- [x] 5.1 引入 canonical descriptor 与 manifest adapter，并在复制前完成全量验证
- [x] 5.2 将 Zotero bootstrap 失败降级为结构化插件状态，同时隔离通用 Agent CLI 单测
- [x] 5.3 覆盖双 schema、Darwin、路径、缺工件、SHA256 与真实 checkout wiring，并同步文档和主规格
