## Context

当前模型代码已从单文件拆分到多个 `server/models_*.py`，但仍处于 `server/` 根目录平铺状态。该结构在语义上不如 `server/models/` 包清晰，也不利于后续按领域持续扩展。与此同时，项目中大量调用方依赖 `from server.models import ...`，因此重构必须保持该公开导入契约稳定。

## Goals / Non-Goals

**Goals:**
- 将模型实现从 `server/models.py` + `server/models_*.py` 迁移为 `server/models/` 包结构。
- 保持 `from server.models import X` 兼容，不引入对外行为变化。
- 清理旧路径导入与残留文件，建立结构守卫防止回退。

**Non-Goals:**
- 不调整模型字段、默认值、校验逻辑和枚举语义。
- 不改 HTTP API、runtime schema/invariants、状态机语义。
- 不在本次重构中引入新的业务能力或外部依赖。

## Decisions

1. 包化落地路径
- 决策：以 `server/models/` 作为唯一模型实现目录，建立 `__init__.py` 作为公开 facade。
- 备选：继续保留 `server/models_*.py` 平铺方式。
- 选择理由：包结构更符合常见约定，边界更清晰，后续扩展成本更低。

2. 公开导入兼容策略
- 决策：在 `server/models/__init__.py` 统一维护 `__all__` 与聚合导出，确保 `from server.models import X` 持续可用。
- 备选：要求调用方改为直接引用子模块（例如 `server.models.run`）。
- 选择理由：可避免大规模调用方改动与回归风险，符合保守兼容目标。

3. 旧文件处理策略
- 决策：迁移完成后删除 `server/models.py` 与 `server/models_*.py` 旧实现文件，不保留重复实现壳。
- 备选：旧文件保留 re-export 壳。
- 选择理由：避免双实现路径长期并存，减少维护负担与循环依赖风险。

4. 导入迁移策略
- 决策：一次性全仓替换内部旧路径导入（`server.models_*`）为包内路径，优先使用包内相对导入。
- 备选：分波迁移并长期容忍双路径。
- 选择理由：一次切换可显著降低长期复杂度与路径漂移。

5. 结构守卫策略
- 决策：更新/新增测试，明确禁止 `server/` 根目录新增 `models_*.py` 并限制 facade 承载实现。
- 备选：仅靠代码评审约束。
- 选择理由：自动化门禁更稳定，可防止组织结构回退。

## Risks / Trade-offs

- [Risk] 包化后导入解析顺序变化可能引发隐藏循环依赖
  -> Mitigation: 迁移时按依赖层次（`common` -> 领域模块 -> facade）重排导入，并跑全量编译与关键回归测试。

- [Risk] 旧路径字符串（测试 monkeypatch / 文本断言）遗漏导致回归
  -> Mitigation: 使用 `rg` 扫描 `server.models_` 与 `server/models_` 残留并在任务中设为门禁项。

- [Risk] 外部或脚本化工具假设 `server/models.py` 文件存在
  -> Mitigation: 在文档中同步新目录结构，并通过结构测试给出明确失败提示。

## Migration Plan

1. 创建 `server/models/` 包并迁移领域模块代码。
2. 将 facade 迁移到 `server/models/__init__.py` 并校准 `__all__`。
3. 批量更新内部导入路径并修复测试 patch 路径。
4. 删除根目录旧模型文件，执行残留扫描确认为 0。
5. 运行指定 pytest + mypy + runtime 合同测试并完成文档同步。

## Open Questions

- 无阻塞性开放问题；按兼容优先策略推进实现。

