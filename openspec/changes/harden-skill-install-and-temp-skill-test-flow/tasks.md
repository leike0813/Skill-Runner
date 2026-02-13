## 1. 安装健壮性增强

- [x] 1.1 将“已安装判定”改为“目录存在且版本可读取”
- [x] 1.2 对无效既有目录执行 `.invalid` 隔离后 fresh install
- [x] 1.3 为无效目录隔离路径增加唯一命名策略
- [x] 1.4 补充单元测试：无效目录 -> 隔离 -> 安装成功

## 2. 测试 demo skill 临时化

- [x] 2.1 suite 增加 `skill_source` / `skill_fixture` 字段（向后兼容）
- [x] 2.2 integration runner 增加 temp-skill 执行路径（内部服务，不走 HTTP）
- [x] 2.3 e2e runner 增加 temp-skill API 路径（`/v1/temp-skill-runs`）
- [x] 2.4 将 demo skill 迁移到 `tests/fixtures/skills/`

## 3. 文档与验证

- [x] 3.1 更新 API 文档（安装健壮性行为）
- [x] 3.2 更新测试文档（suite 新字段与 temp 路径）
- [x] 3.3 运行单元测试与类型检查
