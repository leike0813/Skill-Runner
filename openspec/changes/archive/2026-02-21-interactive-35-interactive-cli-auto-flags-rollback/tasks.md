## 1. Adapter 命令构造回滚

- [x] 1.1 Gemini adapter：interactive 非 resume 回合保留 `--yolo`
- [x] 1.2 Gemini adapter：interactive resume 回合保留 `--yolo`
- [x] 1.3 iFlow adapter：interactive 非 resume 回合保留 `--yolo`
- [x] 1.4 iFlow adapter：interactive resume 回合保留 `--yolo`
- [x] 1.5 Codex adapter：interactive 非 resume 回合保留自动执行参数（`--full-auto`/`--yolo`）
- [x] 1.6 Codex adapter：interactive resume 回合保留自动执行参数（`--full-auto`/`--yolo`）

## 2. 规格与测试同步

- [x] 2.1 新增 `interactive-engine-turn-protocol` 规格增量，声明 interactive 与 resume 保留自动执行参数
- [x] 2.2 更新单测断言：interactive / resume 回合命令包含自动执行参数
- [x] 2.3 运行受影响单测与类型检查，确认无回归
