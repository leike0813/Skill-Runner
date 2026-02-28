## 1. OpenSpec

- [x] 1.1 创建 `services-runtime-engine-reorganization-phase1` 四工件与 delta specs
- [x] 1.2 运行 `openspec validate services-runtime-engine-reorganization-phase1 --type change`

## 2. Runtime Core Migration

- [x] 2.1 迁移 protocol 相关模块到 `server/runtime/protocol/*`
- [x] 2.2 迁移 session 相关模块到 `server/runtime/session/*`
- [x] 2.3 迁移 observability 相关模块到 `server/runtime/observability/*`
- [x] 2.4 迁移 execution 相关模块到 `server/runtime/execution/*`
- [x] 2.5 清理 runtime/* 对 services/* 的反向依赖

## 3. Engine/Common Migration

- [x] 3.1 将 OpenAI 共用协议迁移到 `server/engines/common/openai_auth/*`
- [x] 3.2 下沉 codex TOML 配置管理到 `server/engines/codex/adapter/config/*`
- [x] 3.3 下沉 JSON 配置生成到 `server/engines/common/config/*`
- [x] 3.4 下沉 opencode 模型 catalog 到 `server/engines/opencode/models/*`

## 4. Services Domain Reorganization

- [x] 4.1 services 按域分包（orchestration/skill/ui/platform；不保留 run 子域）
- [x] 4.2 更新全仓 import 到新域路径
- [x] 4.3 删除过时代码与废弃桥接

## 5. Validation

- [x] 5.1 运行 runtime SSOT 回归测试
- [x] 5.2 运行 adapter/auth/UI 关键回归测试
- [x] 5.3 运行 mypy（变更文件集）
