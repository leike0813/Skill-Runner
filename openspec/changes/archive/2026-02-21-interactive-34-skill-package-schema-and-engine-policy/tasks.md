## 1. Manifest Schema 抽离与加载

- [x] 1.1 在 `server/assets/schemas/` 新增 skill package / runner manifest 合同 schema 文件（含 `engines`、`unsupported_engines`、`execution_modes` 等约束）
- [x] 1.2 在 `SkillPackageValidator` 中接入 schema 加载与执行，替换对应硬编码字段校验分支
- [x] 1.3 保留并整合 zip 结构、路径安全、身份一致性、版本比较等非 schema 逻辑，避免行为回归
- [x] 1.4 新增 `input/parameter/output` meta-schema 文件，并定义 Runner 消费扩展键约束
- [x] 1.5 在上传校验阶段对三类 schema 内容执行 meta-schema 预检（安装/临时上传统一）

## 2. Engine Policy 语义实现

- [x] 2.1 实现统一 engine policy 解析：支持 `engines` 可选 + `unsupported_engines` 排除 + 无重叠校验
- [x] 2.2 计算并产出 `effective_engines`，并在结果为空时拒绝 skill 包
- [x] 2.3 安装与临时上传路径统一复用上述 policy 解析逻辑，消除重复实现

## 3. Run 准入与管理 API 联动

- [x] 3.1 在 run 创建入口新增 engine gating：请求引擎不在 `effective_engines` 时返回 `SKILL_ENGINE_UNSUPPORTED`
- [x] 3.2 保持 `execution_mode` 校验与 engine 校验并行生效，明确错误优先级与返回语义
- [x] 3.3 扩展 management skill 响应字段，返回 `effective_engines` 以及原始 `engines`/`unsupported_engines`

## 4. 测试、文档与回归

- [x] 4.1 补充/更新单测：schema 驱动校验、`engines` 缺失默认语义、`unsupported_engines` 冲突与空集合拒绝
- [x] 4.2 补充/更新 API 单测：run 请求命中不支持引擎时的错误码与状态码
- [x] 4.3 更新 `docs/dev_guide.md` 与 `docs/api_reference.md`，明确新的 runner engine 合同与错误语义
- [x] 4.4 运行全量单元测试并修复回归问题，确保实现可验收
- [x] 4.5 补充单测：input/parameter/output meta-schema 预检拒绝非法写法
