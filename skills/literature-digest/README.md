# literature-digest

用于从 MinerU 产出的论文 Markdown（`md_path`）生成：
- `digest`：中文/英文（`zh-CN`/`en-US`）论文摘要 Markdown
- `references`：结构化参考文献条目（JSON 数组）

## 输入

以 `$literature-digest` 调用，并从 prompt 中读取：
- `md_path`：待解析论文 Markdown 路径，唯一内容来源（UTF-8）
- `language`：论文总结语言，`zh-CN`（默认）或 `en-US`

## 输出（stdout）

stdout 仅输出一个 JSON 对象（`literature_digest_v1`），为避免截断只回传文件路径：
- `digest_path`：Markdown 文件路径
- `references_path`：JSON 文件路径（数组）

结果文件默认写入输入文档 `md_path` 所在目录，文件名固定为 `digest.md` 与 `references.json`。

更多细节见 `SKILL.md`。 
