# CodeBuddy Engine Investigation

Date: 2026-07-10

## Purpose

This note records the initial investigation for adding CodyBuddy as a new Skill Runner engine. It focuses on configuration schema and authentication because those areas define most of the integration shape and OpenSpec scope.

No OpenSpec change was created during this investigation, and no implementation files were modified.

## External Kilo Facts

Official CLI documentation:

- CodyBuddy can be launched interactively with `codybuddy`.
- Non-interactive execution uses `codebuddy -p "<task>"`.
- Session import/export and session management are first-class CLI capabilities.
- `codybuddy -p "<task>"` supports stream-JSON output, automatic execution, and session resume flags.

Relevant public sources:

- CLI documentation: <https://www.codebuddy.cn/docs/cli/overview>
- npm package: <https://www.npmjs.com/package/@tencent-ai/codebuddy-code>

Package facts observed from npm:

- Package name: `@tencent-ai/codebuddy-code`
- Binary names: `codebuddy`, `cbc`
- Latest observed version: `2.118.2`
- Install command advertised by the package: `npm install -g @tencent-ai/codebuddy-code`

## Local Probe Findings

Local probe date: 2026-07-10

Observed local installation:

- `codebuddy --version`: `2.118.2`
- `codebuddy` path: `/home/joshua/.nvm/versions/node/v24.12.0/bin/codebuddy`
- `cbc` path: `/home/joshua/.nvm/versions/node/v24.12.0/bin/cbc`

Kilo initializes local state even for help/list commands:

- Default config path: `~/.codebuddy/settings.json`

### Model Catalog

`2.118.2` offers models above:

| Display Name | Model ID |
| --- | --- |
| Hy3 | hy3 |
| GLM-5.2 | glm-5.2 |
| GLM-5.1 | glm-5.1 |
| GLM-5.0 | glm-5.0 |
| GLM-5.0-Turbo | glm-5.0-turbo |
| GLM-5v-Turbo | glm-5v-turbo |
| GLM-4.7 | glm-4.7 |
| MiniMax-M3 | minimax-m3 |
| MiniMax-M2.7 | minimax-m2.7 |
| Kimi-K2.7-Code | kimi-k2.7 |
| Kimi-K2.6 | kimi-k2.6 |
| Kimi-K2.5 | kimi-k2.5 |
| DeepSeek-V4-Pro | deepseek-v4-pro |
| DeepSeek-V4-Flash | deepseek-v4-flash |
| DeepSeek-V3.2 | deepseek-v3-2-volc |

## 执行样例

### 样例1（工具调用与推理）：

- 命令：
```shell
codebuddy --output-format stream-json --permission-mode bypassPermissions -p "去搜索一下美国和伊朗的摩擦的最新情况，然后编写一个脚本，计算从这场摩擦开始到现在经过了多少天，然后找到这个天数的所有质因数分解结果"
```
- stdout输出：`artifacts/codebuddy_stdout_sample-1.jsonl`

### 样例2（多轮对话）：

- 第一轮命令：
```shell
codebuddy --output-format stream-json --permission-mode bypassPermissions -p "尝试问我三个问题，然后从我的回答中推断出我的职业。**要求：每次只能问一个问题，一个一个来。**"
```
- 第一轮stdout输出：`artifacts/codebuddy_stdout_sample-2.attempt-1.jsonl`
- 第二轮命令：
```shell
codebuddy --output-format stream-json --permission-mode bypassPermissions -r c548bd10-7847-4b6e-b557-31f2db1d8b55 -p "codex、vscode、zotero"
```
- 第二轮stdout输出：`artifacts/codebuddy_stdout_sample-2.attempt-2.jsonl`
- 第三轮命令：
```shell
codebuddy --output-format stream-json --permission-mode bypassPermissions -r c548bd10-7847-4b6e-b557-31f2db1d8b55 -p "既有面向学术界的论文，也有面向公众的软件、教程等等，也有给公司内部团队用的产品/报告"
```
- 第三轮stdout输出：`artifacts/codebuddy_stdout_sample-2.attempt-3.jsonl`
- 第四轮命令：
```shell
codebuddy --output-format stream-json --permission-mode bypassPermissions -r c548bd10-7847-4b6e-b557-31f2db1d8b55 -p "写代码、写文章、处理数据"
```
- 第四轮stdout输出：`artifacts/codebuddy_stdout_sample-2.attempt-4.jsonl`
```

