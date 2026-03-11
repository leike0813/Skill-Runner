# Adapter Profile Reference

`adapter_profile.json` 是每个引擎的**配置单源**，位于 `server/engines/<engine>/adapter/adapter_profile.json`。

框架通过此文件驱动 CLI 管理、凭据导入、目录布局、模型目录、缓存键构建等行为，**开发者无需修改任何核心框架代码**即可完成新引擎的适配。

所有路径字段均为**相对于 adapter_profile.json 自身位置**的相对路径，由 profile loader 在加载时解析为绝对路径并做 fail-fast 校验。

---

## 顶层结构

```json
{
  "engine": "<engine_name>",
  "prompt_builder": { ... },
  "session_codec": { ... },
  "attempt_workspace": { ... },
  "config_assets": { ... },
  "model_catalog": { ... },
  "cli_management": { ... }
}
```

---

## `prompt_builder`

提示词模板渲染配置，由 `ProfiledPromptBuilder` 消费。

| 字段 | 类型 | 说明 |
|---|---|---|
| `engine_key` | `str` | 引擎标识，通常与顶层 `engine` 一致 |
| `default_template_path` | `str \| null` | Jinja2 模板文件路径（相对路径） |
| `fallback_inline` | `str` | 模板文件缺失时的内联 fallback |
| `merge_input_if_no_parameter_schema` | `bool` | 无参数 schema 时是否将 input 合并到 prompt |
| `params_json_source` | `"none" \| "input_file" \| "inline"` | 参数 JSON 来源 |
| `main_prompt_source` | `"parameter.prompt" \| "input_prompt"` | 主提示词来源 |
| `main_prompt_default_template` | `str` | 主提示词的默认模板文本 |
| `include_input_file_name` | `bool` | 模板上下文中是否注入输入文件名 |
| `include_skill_dir` | `bool` | 模板上下文中是否注入技能目录路径 |

---

## `session_codec`

交互会话句柄提取配置，由 `ProfiledSessionHandleCodec` 消费。

| 字段 | 类型 | 说明 |
|---|---|---|
| `strategy` | `"json_lines_extract" \| "regex_extract" \| "json_recursive_extract"` | 提取策略 |
| `error_message` | `str` | 提取失败时的错误消息 |
| `error_prefix` | `str \| null` | 错误日志前缀 |
| `required_type` | `str \| null` | 入口 JSON 中 `type` 字段须匹配的值 |
| `id_field` | `str \| null` | JSON 提取时的 ID 字段名 |
| `recursive_key` | `str \| null` | 递归提取时的嵌套键名 |
| `fallback_text_finder` | `object \| null` | 文本 fallback 提取器配置 |
| `json_lines_finder` | `object \| null` | JSON 行扫描器配置（含 `key` 字段） |
| `regex_pattern` | `str \| null` | 正则提取模式 |

策略选择指南：
- 引擎输出 JSON 行 → `json_lines_extract` + `json_lines_finder.key`
- 引擎输出需正则匹配 → `regex_extract` + `regex_pattern`
- 引擎输出 JSON 且 session ID 在嵌套结构中 → `json_recursive_extract`

---

## `attempt_workspace`

run folder 内的目录布局配置，由 `ProfiledWorkspaceProvisioner` 消费。

| 字段 | 类型 | 说明 |
|---|---|---|
| `workspace_subdir` | `str` | 引擎工作目录子目录名（如 `.codex`） |
| `skills_subdir` | `str` | 技能安装子目录名 |
| `use_config_parent_as_workspace` | `bool` | 是否将配置文件父目录作为引擎工作区 |
| `unknown_fallback` | `bool` | 子目录缺失时是否 fallback 到上级目录 |

---

## `config_assets`

引擎运行配置文件路径，由 `ConfigComposer` 和框架各模块消费。

| 字段 | 类型 | 说明 |
|---|---|---|
| `bootstrap_path` | `str` | 引导配置默认值文件路径 |
| `default_path` | `str` | 默认运行配置路径 |
| `enforced_path` | `str` | 强制运行配置路径（优先级最高） |
| `settings_schema_path` | `str \| null` | settings 校验 JSON Schema 路径 |
| `skill_defaults_path` | `str \| null` | 技能级别配置的固定 fallback 文件名定义；运行时会先尝试 `runner.json.engine_configs.<engine>`，失败后再回退到该路径 |

补充说明：
- `config_assets.skill_defaults_path` 不再是唯一的 skill config 来源。
- 运行期解析顺序为：
  1. `runner.json.engine_configs.<engine>`
  2. `config_assets.skill_defaults_path`
- 若声明失败但 fallback 存在：静默回退并记录后台日志。
- 若两者都不存在：视为未提供 skill-specific engine config。

---

## `model_catalog`

模型目录配置，由 `ModelRegistry` 和 `EngineModelCatalogLifecycle` 消费。

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | `"manifest" \| "runtime_probe"` | 模型目录模式 |
| `manifest_path` | `str \| null` | manifest.json 路径 |
| `models_root` | `str \| null` | 模型快照文件根目录 |
| `seed_path` | `str \| null` | 运行时探测的种子文件路径 |

模式说明：
- `manifest`：静态快照模式，通过 `manifest.json` 管理版本化的模型列表。适用于大多数引擎。
- `runtime_probe`：运行时探测模式，引擎在启动时通过 CLI 动态获取模型列表。需实现 `RuntimeProbeCatalogHandler` 并在 `engine_model_catalog_lifecycle.py` 中注册。

---

## `cli_management`

CLI 工具管理配置，由 `AgentCliManager` 消费。

### 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `package` | `str` | npm 包名（安装时使用） |
| `binary_candidates` | `str[]` | CLI 可执行文件候选名列表（跨平台） |

### `credential_imports`

凭据文件导入映射列表：

| 字段 | 类型 | 说明 |
|---|---|---|
| `source` | `str` | 凭据源文件名（在 agent_home 下查找） |
| `target_relpath` | `str` | 目标相对路径（相对 agent_home） |

### `credential_policy`

凭据就绪判定策略：

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | `"all_of_sources" \| "any_of_sources"` | 判定模式 |
| `sources` | `str[]` | 需检查的凭据源文件名列表 |
| `settings_validator` | `"iflow_oauth_settings" \| null` | 可选的 settings 校验器 |

### `resume_probe`

会话恢复能力探测参数：

| 字段 | 类型 | 说明 |
|---|---|---|
| `help_hints` | `str[]` | 帮助文本中用于检测 resume 支持的关键词 |
| `dynamic_args` | `str[]` | 动态探测命令参数（拼接在 CLI 命令后执行） |

### `layout`

目录布局和引导配置：

| 字段 | 类型 | 说明 |
|---|---|---|
| `extra_dirs` | `str[]` | 需创建的额外目录（相对 agent_home） |
| `bootstrap_target_relpath` | `str` | 引导配置写入路径（相对 agent_home） |
| `bootstrap_format` | `"json" \| "text"` | 引导配置文件格式 |
| `normalize_strategy` | `"iflow_settings_v1" \| null` | 可选的 settings 格式标准化策略 |

---

## 完整示例

参见现有引擎的 profile 文件：
- `server/engines/iflow/adapter/adapter_profile.json` — 标准单 provider 引擎的典型配置
- `server/engines/codex/adapter/adapter_profile.json` — 含 `skill_defaults_path` 的配置
- `server/engines/opencode/adapter/adapter_profile.json` — `runtime_probe` 模式模型目录

## 框架消费关系

```text
adapter_profile.json
├── prompt_builder      → ProfiledPromptBuilder
├── session_codec       → ProfiledSessionHandleCodec
├── attempt_workspace   → ProfiledWorkspaceProvisioner
├── config_assets       → ConfigComposer + CacheKeyBuilder + AgentCliManager
├── model_catalog       → ModelRegistry + EngineModelCatalogLifecycle
└── cli_management      → AgentCliManager
    ├── package         → install/upgrade
    ├── binary_candidates → CLI 检测
    ├── credential_*    → 凭据导入与就绪判定
    ├── resume_probe    → 恢复能力探测
    └── layout          → 目录创建与引导配置写入
```
