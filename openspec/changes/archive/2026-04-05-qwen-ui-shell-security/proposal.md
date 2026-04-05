# Proposal: Qwen UI Shell Security Restrictions

## Why

为 Qwen 引擎的 UI shell 配置安全限制，原因是：

1. **UI shell 定位为测试和鉴权工具** - 不需要完整的工具访问权限
2. **防止意外写入工作目录外的文件** - 需要限制文件系统写权限
3. **降低安全风险** - UI shell 会话应该使用最小权限原则
4. **与其他引擎保持一致** - Claude/Opencode 等引擎已有类似的 UI shell 安全配置

## What

本变更为 Qwen UI shell 添加以下安全限制：

### 1. 权限限制（permissions）
- `defaultMode: "dontAsk"` - 默认拒绝未明确允许的操作
- 禁止危险工具：Bash, Edit, Write, Glob, Grep, Read 等
- 不默认允许任何需要权限的操作

### 2. Sandbox 配置
- 明确标注 sandbox 不支持（`static_unsupported`）
- 禁止自动允许 bash（即使在 sandbox 中）
- 禁止 unsandboxed 命令执行

### 3. Session-local 配置
- 通过 `ui_shell_enforced.json` 强制执行安全限制
- 通过 `ui_shell_default.json` 提供默认配置

## How

### 文件变更清单

**新建文件：**
1. `server/engines/qwen/config/ui_shell_default.json` - UI shell 默认配置
2. `server/engines/qwen/config/ui_shell_enforced.json` - UI shell 强制安全配置
3. `openspec/changes/qwen-ui-shell-security/specs/qwen-ui-shell-security/spec.md` - OpenSpec 规范

**修改文件：**
1. `server/engines/qwen/adapter/adapter_profile.json` - 更新 ui_shell.config_assets
2. `server/engines/qwen/schemas/qwen_config_schema.json` - 添加 permissions 和 sandbox schema

### 配置层级

```
default.json (模型选择等默认值)
    ↓
runtime overrides (动态配置，初始为空)
    ↓
enforced.json (强制安全限制)
    ↓
最终 session 配置
```

## Success Criteria

1. UI shell 启动时加载包含安全限制的配置
2. 危险工具（Bash, Edit, Write 等）在 UI shell 模式下被禁止
3. 无法在工作目录外写入文件
4. mypy 类型检查通过
5. 现有测试不受影响
