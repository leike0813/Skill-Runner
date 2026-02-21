## Context

当前 Run 观测页文件预览复用了基于 UTF-8 解码结果的二进制判定逻辑：样本一旦不能严格 UTF-8 解码就会被视为二进制，从而返回“不可预览”。这会把 gb18030、big5 等非 UTF-8 文本误判掉，尤其影响中文 Markdown 的在线排障与核对。

## Goals / Non-Goals

**Goals:**
- 修复 `/ui/runs/{request_id}/view` 对非 UTF-8 文本的误判。
- 二进制判定改为启发式：`NUL` 字节 + 控制字符比例。
- 文本解码按固定回退链路尝试：`utf-8`、`utf-8-sig`、`gb18030`、`big5`。
- 预览元信息能反映实际命中的编码。

**Non-Goals:**
- 不改变 Run 文件浏览的只读和路径安全策略。
- 不改变超大文件降级阈值与行为。
- 不在本 change 内扩展到 Skill 浏览页预览语义（除非实现层复用不改变其外部行为）。

## Decisions

1. Decision: Run 观测页使用独立的文本预览构建逻辑，不再以“UTF-8 解码失败”判二进制。
   - Rationale: 问题只在 Run 观测页需求上被确认，先最小化影响面，避免无 spec 约束地改变 Skill 浏览页行为。
   - Alternative considered: 直接修改 `skill_browser.build_preview_payload` 并让所有页面共享。该方案影响面更大，需要同步修改 `ui-skill-browser` 能力定义，当前先不采用。

2. Decision: 二进制启发式使用“样本含 `NUL` 或控制字符比例超阈值”。
   - 建议样本窗口：前 4KB。
   - 建议控制字符集合：除 `\t`\n`\r` 外的 ASCII C0 控制字符。
   - Rationale: 文本编码多样时，解码失败不能等价于二进制；该启发式能在保留文本容错的同时拦截典型二进制流。

3. Decision: 文本解码采用固定顺序回退并在元信息中标记命中编码。
   - 顺序：`utf-8` → `utf-8-sig` → `gb18030` → `big5`。
   - Rationale: 覆盖当前已知问题编码，顺序稳定可预测，便于测试与运维定位。

## Risks / Trade-offs

- [Risk] 启发式阈值过低导致二进制误判为文本。 → Mitigation: 以 `NUL` 为强信号，并通过单测覆盖含控制字符文本与典型二进制样本。
- [Risk] 回退解码可能将部分损坏字节“强行可读化”。 → Mitigation: 仅在启发式判定为文本后执行，且保留“binary/too_large”降级路径。
- [Risk] 与现有 Skill 预览行为产生差异。 → Mitigation: 本次仅承诺 Run 观测页语义；若要统一，另开 change 修改 `ui-skill-browser` spec。

## Migration Plan

1. 在 Run 观测服务中实现新的预览构建逻辑（含二进制启发式与编码回退）。
2. 保持 UI 路由与模板协议不变，仅调整 preview payload 内容（mode/content/meta）。
3. 增补 Run 观测单测：gb18030/big5 可预览、UTF-8 BOM 可预览、二进制仍降级。
4. 回归现有 UI 路由与预览测试，确保路径安全与大文件降级不回退。

## Open Questions

- 控制字符比例阈值是否需要配置化。当前默认采用常量阈值，后续若出现误判再配置化。
