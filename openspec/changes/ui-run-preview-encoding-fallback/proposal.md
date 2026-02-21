## Why

管理 UI 的 Run 观测页面当前把“不能严格按 UTF-8 解码”的文本文件直接判定为二进制，导致部分合法的非 UTF-8 文本（如 gb18030 编码的 Markdown）被误判为“不可预览”。该问题影响排障与结果核对效率，需要将判定逻辑从“UTF-8 解码是否成功”改为更稳健的启发式。

## What Changes

- 调整 Run 文件预览中的二进制检测策略：
- 不再以 UTF-8 解码失败作为二进制判据。
- 改为“`NUL` 字节 + 控制字符比例”启发式判断二进制。
- 增强文本解码回退链路：
- 依次尝试 `utf-8`、`utf-8-sig`、`gb18030`、`big5`。
- 预览元信息显示实际命中的编码，便于定位来源文件编码。
- 保持只读预览、安全路径约束、超大文件降级等现有行为不变。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `run-observability-ui`: Run 文件预览对非 UTF-8 文本的识别与解码行为调整，避免将可读文本误判为“不可预览”。

## Impact

- Affected code:
- `server/services/run_observability.py`
- `server/services/skill_browser.py`（若复用其预览工具函数）
- `server/routers/ui.py`
- Affected behavior:
- `/ui/runs/{request_id}/view` 在非 UTF-8 文本文件上的预览可用性与编码展示。
- Affected tests/docs:
- Run 观测相关单测（预览场景）与 UI 文档中“不可预览”判定描述。
