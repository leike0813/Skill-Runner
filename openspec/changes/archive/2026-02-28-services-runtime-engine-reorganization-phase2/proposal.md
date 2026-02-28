## Why

phase1 完成目录重组与兼容迁移后，仍会保留部分过渡导入层。为防止架构回流，需要 phase2 做硬切换收口。

## What Changes

1. 删除 phase1 兼容导入层与旧路径别名。
2. 全仓 import 固化到新目录拓扑。
3. 增加静态守卫，禁止回流扁平 services 和旧协议路径。
4. 验证 API/UI 行为仍兼容。

## Scope

### In Scope

- 删除过渡层。
- import 路径硬切换。
- 静态守卫测试与文档固化。

### Out of Scope

- 不新增业务能力。
- 不变更 API 契约。

## Success Criteria

1. 不再存在 phase1 兼容导入层。
2. 关键守卫测试可阻止旧路径回流。
3. 回归测试通过，行为稳定。
