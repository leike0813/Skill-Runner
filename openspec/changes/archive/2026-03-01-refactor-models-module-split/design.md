## Context

`server/models.py` 当前聚合了多域模型，形成典型 god-file。  
该文件被 routers/services/runtime/engines/tests 广泛依赖，直接“按调用方改导入路径”的大迁移成本高且风险大。  
因此采用“实现拆分 + 兼容 façade”策略：内部按域拆分，外部保持 `server.models` 稳定导入。

## Goals / Non-Goals

**Goals**
- 将 `server/models.py` 拆分为多文件、按域维护。
- 保留 `from server.models import ...` 的兼容导出能力。
- 保持对外 API 与 runtime 协议语义不变。
- 增加结构守卫测试，避免文件体量反弹。

**Non-Goals**
- 不重命名模型类或字段。
- 不修改 HTTP API 类型契约。
- 不调整 runtime schema/invariants。
- 不在本次变更中引入额外依赖。

## Decisions

### 1) 分域模块划分
新增以下模块（命名固定）：
- `server/models_common.py`
- `server/models_run.py`
- `server/models_skill.py`
- `server/models_engine.py`
- `server/models_interaction.py`
- `server/models_management.py`
- `server/models_runtime_event.py`
- `server/models_error.py`

### 2) `server/models.py` 作为兼容聚合层
- `server/models.py` 不再定义核心模型实现。
- 仅负责从分域模块 re-export 公共模型。
- 保留现有外部导入路径和符号命名。

### 3) 保守迁移策略
- 第一阶段：纯搬迁定义，确保行为等价。
- 第二阶段：更新内部引用为“可选按域导入”（仅限同域内部实现，外部调用方可维持 `server.models`）。
- 第三阶段：添加结构守卫测试与文件大小约束（例如 `models.py` 行数阈值）。

### 4) 质量门禁
- 运行现有 runtime/management/interactive 关键回归测试，确保合同语义未漂移。
- 新增结构守卫测试检查：
  - `server/models.py` 不含大量 `class <Name>(BaseModel|Enum)` 实现
  - 行数不超过约定阈值（建议 `<= 220`）

## Risks / Trade-offs

- [Risk] re-export 漏项导致运行时 ImportError。  
  -> Mitigation: 增加导出完整性测试，覆盖关键模型列表。

- [Risk] 搬迁过程误改字段默认值或 Optional 语义。  
  -> Mitigation: 优先复制粘贴搬迁，不做语义改写；跑关键回归测试。

- [Risk] 结构守卫过严影响后续演进。  
  -> Mitigation: 采用可解释阈值 + 明确例外规则（仅聚合定义可留在 `models.py`）。

## Migration Plan

1. 先创建分域模型文件并迁移定义（无语义变化）。
2. 将 `server/models.py` 改为聚合导出层。
3. 补充/更新测试（导出完整性 + 结构守卫）。
4. 运行核心回归测试与 mypy。
5. 确认 `server/models.py` 体量显著下降并可长期守卫。
