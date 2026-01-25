# 运行中间产物 (Run Intermediate Artifacts)

本文档描述在一次技能执行 (Run) 过程中，系统在 `data/runs/<run_id>/` 目录下生成的各类中间文件及其格式模版。

## 目录结构

```text
data/runs/<run_id>/
├── uploads/           # 用户上传文件
│   └── <input_file>
├── artifacts/         # 技能输出产物
├── result/            # 结构化结果
├── logs/              # 执行日志
│   ├── prompt.txt     # 生成的最终 Prompt
│   ├── stdout.txt     # CLI 标准输出
│   └── stderr.txt     # CLI 标准错误
├── bundle/            # 运行结果打包
│   ├── run_bundle.zip
│   ├── run_bundle_debug.zip
│   ├── manifest.json
│   └── manifest_debug.json
└── .gemini/           # 运行时环境
    └── skills/        # 技能副本
```

## 1. `logs/prompt.txt`

这是提交给 LLM 的最终指令，由 `GeminiAdapter` 根据 `runner.json` 和 Jinja2 模板生成。

**生成逻辑**:
1. **模板选择**: 
   - 优先检查 `runner.json` 中的 `entrypoint.prompts.gemini` 是否定义了自定义模板。
   - 若未定义，则使用 `GeminiAdapter` 内置的通用默认模板。
2. **上下文注入**: 
   - 注入 `{{ input }}` (已解析的文件绝对路径字典).
   - 注入 `{{ parameter }}` (配置参数字典).
   - 注入 `SKILL.md` 内容.
3. **渲染**: 使用 Jinja2 生成最终文本。

**模版示例**:

```markdown
请调用名为 'demo-prime-number' 的技能。

# Inputs

- input_file: /home/user/project/data/runs/<uuid>/uploads/input.txt

# Parameters

- divisor: 1

Task: Execute the skill using the above inputs and parameters.
```

## 2. `logs/stdout.txt`

记录底层 CLI (Gemini CLI) 执行时的标准输出流。

**模版示例**:

```text
[INFO] Loading skill: demo-prime-number
[INFO] Reading input file: /home/user/project/data/runs/<uuid>/uploads/input.txt
[RESULT]
{
  "primes": [2, 3, 5, 7],
  "count": 4
}
```

## 3. `logs/stderr.txt`

记录底层 CLI 执行时的错误输出或调试信息。

**模版示例**:

```text
(node:12345) ExperimentalWarning: The Fetch API is an experimental feature...
```

## 4. `input.json` (请求审计与状态持久化)

该文件主要用于**审计 (Audit)** 和 **状态恢复**，记录了 Client 发起请求时的原始 JSON Payload。

**为什么要保留它？**
- 虽然底层 CLI (Gemini) 直接通过命令行接收 Prompt，并不读取此文件，但系统需要持久化用户的原始请求以便重试或调试。
- **关于 Input/Parameter 混合**: 由于 HTTP API 的设计通常接受一个统一的 JSON Body，这个文件忠实记录了 API 接收到的原始数据。但在执行阶段（见 `logs/prompt.txt`），系统会严格根据 Schema 将其拆解为 `input` (文件) 和 `parameter` (参数) 两个独立的上下文。

**结构示例**:
```json
{
  "skill_id": "demo-prime-number",
  "parameter": { 
    "divisor": 1
  }
}
```

## 5. `result/result.json`

执行完成后的统一结果文件，包含标准化状态、数据、产物列表与错误信息。

**示例**:
```json
{
  "status": "failed",
  "data": null,
  "artifacts": ["artifacts/primes.md"],
  "validation_warnings": [],
  "error": {"message": "Missing required input files: input_file", "stderr": ""}
}
```

## 6. `bundle/`

用于下载的运行打包结果：
- `run_bundle.zip`：debug=false 时生成
- `run_bundle_debug.zip`：debug=true 时生成
- `manifest.json`/`manifest_debug.json`：对应 bundle 的文件清单

## 7. `.gemini/skills/<skill_id>/`

这是一个**完全独立**的技能环境副本。即使用户修改了原始 `skills/` 目录下的文件，正在运行的任务也不会受到影响。

包含：
- `assets/` (runner.json, schemas)
- `SKILL.md`
- 其他辅助脚本
