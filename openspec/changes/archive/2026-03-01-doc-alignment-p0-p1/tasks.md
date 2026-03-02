## 1. P0: SSOT 路径修正

- [x] 1.1 更新 `AGENTS.md` 中 7 条过期 SSOT 源代码路径（`server/services/session_statechart.py` → `server/runtime/session/statechart.py` 等）
- [x] 1.2 更新 `docs/session_runtime_statechart_ssot.md` 中 3 处实现锚点路径
- [x] 1.3 验证：对所有修正路径执行 `test -f` 确认文件存在

## 2. P1: 结构类文档重写

- [x] 2.1 重写 `docs/project_structure.md`：从实际文件系统生成 `server/` 目录树，标注各层职责
- [x] 2.2 重写 `docs/core_components.md`：按 Runtime/Services/Engines/Routers 四层描述组件路径与职责
- [x] 2.3 更新 `README.md`：添加 OpenCode 引擎到支持列表、更新架构简述、更新鉴权配置说明

## 3. P2: 设计类文档局部更新

- [x] 3.1 在 `docs/dev_guide.md` 文件头添加归档告警标注
- [x] 3.2 更新 `docs/adapter_design.md`：方法签名对齐当前组件模型、标记 §3 重构计划为已完成
- [x] 3.3 更新 `docs/test_framework_design.md`：单元测试目录规划对齐当前测试文件分类

## 4. 验证

- [x] 4.1 全量路径校验：提取所有文档中的 `.py` 路径引用，逐一验证存在性
