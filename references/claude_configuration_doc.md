# Claude Code 设置 - Claude Code Docs
Claude Code 提供多种设置来配置其行为以满足您的需求。您可以在使用交互式 REPL 时运行 `/config` 命令来配置 Claude Code，这会打开一个选项卡式设置界面，您可以在其中查看状态信息并修改配置选项。

配置作用域
-----

Claude Code 使用**作用域系统**来确定配置应用的位置以及与谁共享。了解作用域可以帮助您决定如何为个人使用、团队协作或企业部署配置 Claude Code。

### 可用作用域


|作用域    |位置                                            |影响范围       |与团队共享？       |
|-------|----------------------------------------------|-----------|-------------|
|Managed|服务器管理的设置、plist / 注册表或系统级 managed-settings.json|机器上的所有用户   |是（由 IT 部署）   |
|User   |~/.claude/ 目录                                 |您，跨所有项目    |否            |
|Project|存储库中的 .claude/                                |此存储库上的所有协作者|是（提交到 git）   |
|Local  |.claude/settings.local.json                   |您，仅在此存储库中  |否（gitignored）|


### 何时使用每个作用域

**Managed 作用域**用于：

*   必须在整个组织范围内强制执行的安全策略
*   无法被覆盖的合规要求
*   由 IT/DevOps 部署的标准化配置

**User 作用域**最适合：

*   您想在任何地方使用的个人偏好设置（主题、编辑器设置）
*   您在所有项目中使用的工具和插件
*   API 密钥和身份验证（安全存储）

**Project 作用域**最适合：

*   团队共享的设置（权限、hooks、MCP servers）
*   整个团队应该拥有的插件
*   跨协作者标准化工具

**Local 作用域**最适合：

*   特定项目的个人覆盖
*   在与团队共享之前测试配置
*   对其他人不适用的特定于机器的设置

### 作用域如何相互作用

当在多个作用域中配置相同的设置时，更具体的作用域优先：

1.  **Managed**（最高）- 无法被任何内容覆盖
2.  **命令行参数** - 临时会话覆盖
3.  **Local** - 覆盖项目和用户设置
4.  **Project** - 覆盖用户设置
5.  **User**（最低）- 当没有其他内容指定设置时应用

例如，如果在用户设置中允许某个权限，但在项目设置中拒绝，则项目设置优先，权限被阻止。

### 哪些功能使用作用域

作用域适用于许多 Claude Code 功能：


|功能         |User 位置                |Project 位置                   |Local 位置                   |
|-----------|-----------------------|-----------------------------|---------------------------|
|Settings   |~/.claude/settings.json|.claude/settings.json        |.claude/settings.local.json|
|Subagents  |~/.claude/agents/      |.claude/agents/              |无                          |
|MCP servers|~/.claude.json         |.mcp.json                    |~/.claude.json（每个项目）       |
|Plugins    |~/.claude/settings.json|.claude/settings.json        |.claude/settings.local.json|
|CLAUDE.md  |~/.claude/CLAUDE.md    |CLAUDE.md 或 .claude/CLAUDE.md|无                          |


* * *

设置文件
----

`settings.json` 文件是通过分层设置配置 Claude Code 的官方机制：

*   **用户设置**在 `~/.claude/settings.json` 中定义，适用于所有项目。
*   **项目设置**保存在您的项目目录中：
    *   `.claude/settings.json` 用于检入源代码管理并与您的团队共享的设置
    *   `.claude/settings.local.json` 用于未检入的设置，适用于个人偏好和实验。Claude Code 将在创建 `.claude/settings.local.json` 时配置 git 以忽略它。
*   **Managed 设置**：对于需要集中控制的组织，Claude Code 支持多种 managed 设置的交付机制。所有机制都使用相同的 JSON 格式，无法被用户或项目设置覆盖：
    
    *   **服务器管理的设置**：通过 Claude.ai 管理员控制台从 Anthropic 的服务器交付。请参阅[服务器管理的设置](https://code.claude.com/docs/zh-CN/server-managed-settings)。
    *   **MDM/OS 级别策略**：通过 macOS 和 Windows 上的本机设备管理交付：
        *   macOS：`com.anthropic.claudecode` managed preferences 域（通过 Jamf、Kandji 或其他 MDM 工具中的配置文件部署）
        *   Windows：`HKLM\SOFTWARE\Policies\ClaudeCode` 注册表项，带有包含 JSON 的 `Settings` 值（REG\_SZ 或 REG\_EXPAND\_SZ）（通过组策略或 Intune 部署）
        *   Windows（用户级）：`HKCU\SOFTWARE\Policies\ClaudeCode`（最低策略优先级，仅在不存在管理员级源时使用）
    *   **基于文件**：`managed-settings.json` 和 `managed-mcp.json` 部署到系统目录：
        
        *   macOS：`/Library/Application Support/ClaudeCode/`
        *   Linux 和 WSL：`/etc/claude-code/`
        *   Windows：`C:\Program Files\ClaudeCode\`
        
        基于文件的 managed 设置还支持在与 `managed-settings.json` 相同的系统目录中的 `managed-settings.d/` 放入目录。这让独立的团队可以部署独立的策略片段，而无需协调对单个文件的编辑。 遵循 systemd 约定，`managed-settings.json` 首先作为基础合并，然后放入目录中的所有 `*.json` 文件按字母顺序排序并合并在顶部。对于标量值，后面的文件覆盖前面的文件；数组被连接和去重；对象被深度合并。以 `.` 开头的隐藏文件被忽略。 使用数字前缀来控制合并顺序，例如 `10-telemetry.json` 和 `20-security.json`。
    
    请参阅 [managed 设置](about:/docs/zh-CN/permissions#managed-only-settings) 和 [Managed MCP 配置](about:/docs/zh-CN/mcp#managed-mcp-configuration) 了解详情。
*   **其他配置**存储在 `~/.claude.json` 中。此文件包含您的偏好设置（主题、通知设置、编辑器模式）、OAuth 会话、[MCP server](https://code.claude.com/docs/zh-CN/mcp) 配置（用于用户和本地作用域）、每个项目的状态（允许的工具、信任设置）和各种缓存。项目作用域的 MCP servers 单独存储在 `.mcp.json` 中。

```
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(npm run lint)",
      "Bash(npm run test *)",
      "Read(~/.zshrc)"
    ],
    "deny": [
      "Bash(curl *)",
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  },
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp"
  },
  "companyAnnouncements": [
    "Welcome to Acme Corp! Review our code guidelines at docs.acme.com",
    "Reminder: Code reviews required for all PRs",
    "New security policy in effect"
  ]
}

```


上面示例中的 `$schema` 行指向 Claude Code 设置的[官方 JSON 架构](https://json.schemastore.org/claude-code-settings.json)。将其添加到您的 `settings.json` 可在 VS Code、Cursor 和任何其他支持 JSON 架构验证的编辑器中启用自动完成和内联验证。

### 可用设置

`settings.json` 支持多个选项：



* 键: agent
  * 描述: 将主线程作为命名 subagent 运行。应用该 subagent 的系统提示、工具限制和模型。请参阅显式调用 subagents
  * 示例: "code-reviewer"
* 键: allowedChannelPlugins
  * 描述: （仅 Managed 设置）可能推送消息的频道插件的允许列表。设置后替换默认 Anthropic 允许列表。未定义 = 回退到默认值，空数组 = 阻止所有频道插件。需要 channelsEnabled: true。请参阅限制哪些频道插件可以运行
  * 示例: [{ "marketplace": "claude-plugins-official", "plugin": "telegram" }]
* 键: allowedHttpHookUrls
  * 描述: HTTP hooks 可能针对的 URL 模式的允许列表。支持 * 作为通配符。设置后，具有不匹配 URL 的 hooks 被阻止。未定义 = 无限制，空数组 = 阻止所有 HTTP hooks。数组跨设置源合并。请参阅 Hook 配置
  * 示例: ["https://hooks.example.com/*"]
* 键: allowedMcpServers
  * 描述: 在 managed-settings.json 中设置时，用户可以配置的 MCP servers 的允许列表。未定义 = 无限制，空数组 = 锁定。适用于所有作用域。拒绝列表优先。请参阅 Managed MCP 配置
  * 示例: [{ "serverName": "github" }]
* 键: allowManagedHooksOnly
  * 描述: （仅 Managed 设置）防止加载用户、项目和插件 hooks。仅允许 managed hooks 和 SDK hooks。请参阅 Hook 配置
  * 示例: true
* 键: allowManagedMcpServersOnly
  * 描述: （仅 Managed 设置）仅尊重来自 managed 设置的 allowedMcpServers。deniedMcpServers 仍从所有源合并。用户仍可以添加 MCP servers，但仅应用管理员定义的允许列表。请参阅 Managed MCP 配置
  * 示例: true
* 键: allowManagedPermissionRulesOnly
  * 描述: （仅 Managed 设置）防止用户和项目设置定义 allow、ask 或 deny 权限规则。仅应用 managed 设置中的规则。请参阅 Managed 专用设置
  * 示例: true
* 键: alwaysThinkingEnabled
  * 描述: 为所有会话默认启用扩展思考。通常通过 /config 命令而不是直接编辑来配置
  * 示例: true
* 键: apiKeyHelper
  * 描述: 自定义脚本，在 /bin/sh 中执行，以生成身份验证值。此值将作为 X-Api-Key 和 Authorization: Bearer 标头发送用于模型请求
  * 示例: /bin/generate_temp_api_key.sh
* 键: attribution
  * 描述: 自定义 git 提交和拉取请求的归属。请参阅归属设置
  * 示例: {"commit": "🤖 Generated with Claude Code", "pr": ""}
* 键: autoMemoryDirectory
  * 描述: 自动内存存储的自定义目录。接受 ~/ 扩展的路径。不在项目设置（.claude/settings.json）中接受，以防止共享存储库将内存写入重定向到敏感位置。从策略、本地和用户设置接受
  * 示例: "~/my-memory-dir"
* 键: autoMode
  * 描述: 自定义自动模式分类器阻止和允许的内容。包含 environment、allow 和 soft_deny 散文规则数组。请参阅配置自动模式分类器。不从共享项目设置读取
  * 示例: {"environment": ["Trusted repo: github.example.com/acme"]}
* 键: autoUpdatesChannel
  * 描述: 遵循更新的发布渠道。使用 "stable" 获取通常约一周前的版本并跳过有主要回归的版本，或使用 "latest"（默认）获取最新版本
  * 示例: "stable"
* 键: availableModels
  * 描述: 限制用户可以通过 /model、--model、Config 工具或 ANTHROPIC_MODEL 选择的模型。不影响默认选项。请参阅限制模型选择
  * 示例: ["sonnet", "haiku"]
* 键: awsAuthRefresh
  * 描述: 修改 .aws 目录的自定义脚本（请参阅高级凭证配置）
  * 示例: aws sso login --profile myprofile
* 键: awsCredentialExport
  * 描述: 输出包含 AWS 凭证的 JSON 的自定义脚本（请参阅高级凭证配置）
  * 示例: /bin/generate_aws_grant.sh
* 键: blockedMarketplaces
  * 描述: （仅 Managed 设置）市场源的阻止列表。在下载前检查被阻止的源，因此它们永远不会接触文件系统。请参阅 Managed 市场限制
  * 示例: [{ "source": "github", "repo": "untrusted/plugins" }]
* 键: channelsEnabled
  * 描述: （仅 Managed 设置）为 Team 和 Enterprise 用户允许 channels。未设置或 false 会阻止频道消息传递，无论用户传递什么给 --channels
  * 示例: true
* 键: cleanupPeriodDays
  * 描述: 非活跃时间超过此期间的会话在启动时被删除（默认：30 天，最少 1 天）。设置为 0 会被拒绝并显示验证错误。要在非交互模式（-p）中完全禁用记录写入，请使用 --no-session-persistence 标志或 persistSession: false SDK 选项；没有交互模式等效项。
  * 示例: 20
* 键: companyAnnouncements
  * 描述: 在启动时显示给用户的公告。如果提供多个公告，它们将随机循环显示。
  * 示例: ["Welcome to Acme Corp! Review our code guidelines at docs.acme.com"]
* 键: defaultShell
  * 描述: 输入框 ! 命令的默认 shell。接受 "bash"（默认）或 "powershell"。设置 "powershell" 会在 Windows 上通过 PowerShell 路由交互式 ! 命令。需要 CLAUDE_CODE_USE_POWERSHELL_TOOL=1。请参阅 PowerShell tool
  * 示例: "powershell"
* 键: deniedMcpServers
  * 描述: 在 managed-settings.json 中设置时，明确阻止的 MCP servers 的拒绝列表。适用于所有作用域，包括 managed servers。拒绝列表优先于允许列表。请参阅 Managed MCP 配置
  * 示例: [{ "serverName": "filesystem" }]
* 键: disableAllHooks
  * 描述: 禁用所有 hooks 和任何自定义状态行
  * 示例: true
* 键: disableAutoMode
  * 描述: 设置为 "disable" 以防止自动模式被激活。从 Shift+Tab 循环中删除 auto 并在启动时拒绝 --permission-mode auto。在managed 设置中最有用，用户无法覆盖它
  * 示例: "disable"
* 键: disableDeepLinkRegistration
  * 描述: 设置为 "disable" 以防止 Claude Code 在启动时向操作系统注册 claude-cli:// 协议处理程序。深链接让外部工具通过 claude-cli://open?q=... 使用预填充的提示打开 Claude Code 会话。在协议处理程序注册受限或单独管理的环境中很有用
  * 示例: "disable"
* 键: disabledMcpjsonServers
  * 描述: 要拒绝的 .mcp.json 文件中特定 MCP servers 的列表
  * 示例: ["filesystem"]
* 键: effortLevel
  * 描述: 跨会话持久化努力级别。接受 "low"、"medium" 或 "high"。当您运行 /effort low、/effort medium 或 /effort high 时自动写入。在 Opus 4.6 和 Sonnet 4.6 上支持
  * 示例: "medium"
* 键: enableAllProjectMcpServers
  * 描述: 自动批准项目 .mcp.json 文件中定义的所有 MCP servers
  * 示例: true
* 键: enabledMcpjsonServers
  * 描述: 要批准的 .mcp.json 文件中特定 MCP servers 的列表
  * 示例: ["memory", "github"]
* 键: env
  * 描述: 将应用于每个会话的环境变量
  * 示例: {"FOO": "bar"}
* 键: fastModePerSessionOptIn
  * 描述: 当为 true 时，快速模式不会跨会话持久化。每个会话都以快速模式关闭开始，需要用户使用 /fast 启用它。用户的快速模式偏好仍被保存。请参阅需要每个会话的选择加入
  * 示例: true
* 键: feedbackSurveyRate
  * 描述: 概率（0–1）会话质量调查在符合条件时出现。设置为 0 以完全抑制。在使用 Bedrock、Vertex 或 Foundry 时很有用，其中默认采样率不适用
  * 示例: 0.05
* 键: fileSuggestion
  * 描述: 为 @ 文件自动完成配置自定义脚本。请参阅文件建议设置
  * 示例: {"type": "command", "command": "~/.claude/file-suggestion.sh"}
* 键: forceLoginMethod
  * 描述: 使用 claudeai 限制登录到 Claude.ai 账户，console 限制登录到 Claude Console（API 使用计费）账户
  * 示例: claudeai
* 键: forceLoginOrgUUID
  * 描述: 要求登录属于特定组织。接受单个 UUID 字符串（也在登录期间预选该组织）或 UUID 数组，其中任何列出的组织都被接受而无需预选。在 managed 设置中设置时，如果经过身份验证的账户不属于列出的组织，登录失败；空数组失败关闭并使用配置错误消息阻止登录
  * 示例: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" 或 ["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"]
* 键: hooks
  * 描述: 配置自定义命令以在生命周期事件处运行。请参阅 hooks 文档 了解格式
  * 示例: 请参阅 hooks
* 键: httpHookAllowedEnvVars
  * 描述: HTTP hooks 可能插入到标头中的环境变量名称的允许列表。设置后，每个 hook 的有效 allowedEnvVars 是与此列表的交集。未定义 = 无限制。数组跨设置源合并。请参阅 Hook 配置
  * 示例: ["MY_TOKEN", "HOOK_SECRET"]
* 键: includeCoAuthoredBy
  * 描述: 已弃用：改用 attribution。是否在 git 提交和拉取请求中包含 co-authored-by Claude 署名（默认：true）
  * 示例: false
* 键: includeGitInstructions
  * 描述: 在 Claude 的系统提示中包含内置提交和 PR 工作流说明和 git 状态快照（默认：true）。设置为 false 以删除这两者，例如在使用您自己的 git 工作流 skills 时。CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS 环境变量在设置时优先于此设置
  * 示例: false
* 键: language
  * 描述: 配置 Claude 的首选响应语言（例如 "japanese"、"spanish"、"french"）。Claude 将默认以此语言响应。也设置语音听写语言
  * 示例: "japanese"
* 键: model
  * 描述: 覆盖用于 Claude Code 的默认模型
  * 示例: "claude-sonnet-4-6"
* 键: modelOverrides
  * 描述: 将 Anthropic 模型 ID 映射到特定于提供商的模型 ID，例如 Bedrock 推理配置文件 ARN。每个模型选择器条目在调用提供商 API 时使用其映射值。请参阅按版本覆盖模型 ID
  * 示例: {"claude-opus-4-6": "arn:aws:bedrock:..."}
* 键: otelHeadersHelper
  * 描述: 生成动态 OpenTelemetry 标头的脚本。在启动时和定期运行（请参阅动态标头）
  * 示例: /bin/generate_otel_headers.sh
* 键: outputStyle
  * 描述: 配置输出样式以调整系统提���。请参阅输出样式文档
  * 示例: "Explanatory"
* 键: permissions
  * 描述: 请参阅下表了解权限的结构。
  * 示例: 
* 键: plansDirectory
  * 描述: 自定义计划文件的存储位置。路径相对于项目根目录。默认：~/.claude/plans
  * 示例: "./plans"
* 键: pluginTrustMessage
  * 描述: （仅 Managed 设置）在安装前显示的插件信任警告中附加的自定义消息。使用此添加组织特定的上下文，例如确认来自您内部市场的插件已获批准。
  * 示例: "All plugins from our marketplace are approved by IT"
* 键: prefersReducedMotion
  * 描述: 减少或禁用 UI 动画（微调器、闪烁、闪光效果）以实现可访问性
  * 示例: true
* 键: respectGitignore
  * 描述: 控制 @ 文件选择器是否尊重 .gitignore 模式。当为 true（默认）时，匹配 .gitignore 模式的文件被排除在建议之外
  * 示例: false
* 键: showClearContextOnPlanAccept
  * 描述: 在计划接受屏幕上显示”清除上下文”选项。默认为 false。设置为 true 以恢复该选项
  * 示例: true
* 键: showThinkingSummaries
  * 描述: 在交互式会话中显示扩展思考摘要。未设置或 false（交互模式中的默认值）时，思考块由 API 编辑并显示为折叠的存根。编辑仅改变您看到的内容，而不是模型生成的内容：要减少思考支出，降低预算或禁用思考。非交互模式（-p）和 SDK 调用者无论此设置如何都始终接收摘要
  * 示例: true
* 键: spinnerTipsEnabled
  * 描述: 在 Claude 工作时在微调器中显示提示。设置为 false 以禁用提示（默认：true）
  * 示例: false
* 键: spinnerTipsOverride
  * 描述: 使用自定义字符串覆盖微调器提示。tips：提示字符串数组。excludeDefault：如果为 true，仅显示自定义提示；如果为 false 或不存在，自定义提示与内置提示合并
  * 示例: { "excludeDefault": true, "tips": ["Use our internal tool X"] }
* 键: spinnerVerbs
  * 描述: 自定义在微调器和轮次持续时间消息中显示的操作动词。将 mode 设置为 "replace" 以仅使用您的动词，或 "append" 以将它们添加到默认值
  * 示例: {"mode": "append", "verbs": ["Pondering", "Crafting"]}
* 键: statusLine
  * 描述: 配置自定义状态行以显示上下文。请参阅statusLine 文档
  * 示例: {"type": "command", "command": "~/.claude/statusline.sh"}
* 键: strictKnownMarketplaces
  * 描述: （仅 Managed 设置）用户可以添加的插件市场的允许列表。未定义 = 无限制，空数组 = 锁定。仅适用于市场添加。请参阅 Managed 市场限制
  * 示例: [{ "source": "github", "repo": "acme-corp/plugins" }]
* 键: useAutoModeDuringPlan
  * 描述: Plan Mode 在自动模式可用时是否使用自动模式语义。默认：true。不从共享项目设置读取。在 /config 中显示为”在计划期间使用自动模式”
  * 示例: false
* 键: voiceEnabled
  * 描述: 启用推送说话语音听写。当您运行 /voice 时自动写入。需要 Claude.ai 账户
  * 示例: true


### 全局配置设置

这些设置存储在 `~/.claude.json` 中，而不是 `settings.json`。将它们添加到 `settings.json` 将触发架构验证错误。



* 键: autoConnectIde
  * 描述: 当 Claude Code 从外部终端启动时自动连接到运行的 IDE。默认：false。在 VS Code 或 JetBrains 终端外运行时在 /config 中显示为自动连接到 IDE（外部终端）
  * 示例: true
* 键: autoInstallIdeExtension
  * 描述: 从 VS Code 终端运行时自动安装 Claude Code IDE 扩展。默认：true。在 VS Code 或 JetBrains 终端内运行时在 /config 中显示为自动安装 IDE 扩展。您也可以设置 CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL 环境变量
  * 示例: false
* 键: editorMode
  * 描述: 输入提示的快捷键模式："normal" 或 "vim"。默认："normal"。当您运行 /vim 时自动写入。在 /config 中显示为快捷键模式
  * 示例: "vim"
* 键: showTurnDuration
  * 描述: 在响应后显示轮次持续时间消息，例如”Cooked for 1m 6s”。默认：true。在 /config 中显示为显示轮次持续时间
  * 示例: false
* 键: terminalProgressBarEnabled
  * 描述: 在支持的终端中显示终端进度条：ConEmu、Ghostty 1.2.0+ 和 iTerm2 3.6.6+。默认：true。在 /config 中显示为终端进度条
  * 示例: false
* 键: teammateMode
  * 描述: agent team 队友的显示方式：auto（在 tmux 或 iTerm2 中选择分割窗格，否则进程内）、in-process 或 tmux。请参阅选择显示模式
  * 示例: "in-process"


### Worktree 设置

配置 `--worktree` 如何创建和管理 git worktrees。使用这些设置来减少大型 monorepos 中的磁盘使用和启动时间。



* 键: worktree.symlinkDirectories
  * 描述: 要从主存储库符号链接到每个 worktree 的目录，以避免在磁盘上复制大型目录。默认情况下不符号链接任何目录
  * 示例: ["node_modules", ".cache"]
* 键: worktree.sparsePaths
  * 描述: 通过 git sparse-checkout（cone 模式）在每个 worktree 中检出的目��。仅将列出的路径写入磁盘，在大型 monorepos 中更快
  * 示例: ["packages/my-app", "shared/utils"]


要将 gitignored 文件（如 `.env`）复制到新的 worktrees，请在项目根目录中使用 [`.worktreeinclude` 文件](about:/docs/zh-CN/common-workflows#copy-gitignored-files-to-worktrees)，而不是设置。

### 权限设置



* 键: allow
  * 描述: 允许工具使用的权限规则数组。请参阅下面的权限规则语法了解模式匹配详情
  * 示例: [ "Bash(git diff *)" ]
* 键: ask
  * 描述: 在工具使用时要求确认的权限规则数组。请参阅下面的权限规则语法
  * 示例: [ "Bash(git push *)" ]
* 键: deny
  * 描述: 拒绝工具使用的权限规则数组。使用此排除敏感文件不被 Claude Code 访问。请参阅权限规则语法和 Bash 权限限制
  * 示例: [ "WebFetch", "Bash(curl *)", "Read(./.env)", "Read(./secrets/**)" ]
* 键: additionalDirectories
  * 描述: Claude 有权访问的额外工作目录。大多数 .claude/ 配置未从这些目录发现
  * 示例: [ "../docs/" ]
* 键: defaultMode
  * 描述: 打开 Claude Code 时的默认权限模式。有效值：default、acceptEdits��plan、auto、dontAsk、bypassPermissions。--permission-mode CLI 标志覆盖此设置用于单个会话
  * 示例: "acceptEdits"
* 键: disableBypassPermissionsMode
  * 描述: 设置为 "disable" 以防止激活 bypassPermissions 模式。禁用 --dangerously-skip-permissions 标志。在managed 设置中最有用，用户无法覆盖它
  * 示例: "disable"
* 键: skipDangerousModePermissionPrompt
  * 描述: 跳过通过 --dangerously-skip-permissions 或 defaultMode: "bypassPermissions" 进入 bypass permissions 模式前显示的确认提示。在项目设置（.claude/settings.json）中设置时被忽略，以防止不受信任的存储库自动绕过提示
  * 示例: true


### 权限规则语法

权限规则遵循 `Tool` 或 `Tool(specifier)` 的格式。规则按顺序评估：首先是拒绝规则，然后是询问，最后是允许。第一个匹配的规则获胜。 快速示例：


|规则                          |效果                   |
|----------------------------|---------------------|
|Bash                        |匹配所有 Bash 命令         |
|Bash(npm run *)             |匹配以 npm run 开头的命令    |
|Read(./.env)                |匹配读取 .env 文件         |
|WebFetch(domain:example.com)|匹配对 example.com 的获取请求|


有关完整的规则语法参考，包括通配符行为、Read、Edit、WebFetch、MCP 和 Agent 规则的工具特定模式，以及 Bash 模式的安全限制，请参阅[权限规则语法](about:/docs/zh-CN/permissions#permission-rule-syntax)。

### Sandbox 设置

配置高级 sandboxing 行为。Sandboxing 将 bash 命令与您的文件系统和网络隔离。请参阅 [Sandboxing](https://code.claude.com/docs/zh-CN/sandboxing) 了解详情。



* 键: enabled
  * 描述: 启用 bash sandboxing（macOS、Linux 和 WSL2）。默认：false
  * 示例: true
* 键: failIfUnavailable
  * 描述: 如果 sandbox.enabled 为 true 但 sandbox 无法启动（缺少依赖项、不支持的平台或平台限制），则在启动时以错误退出。当为 false（默认）时，显示警告，命令无 sandbox 运行。用于需要 sandboxing 作为硬门的 managed 设置部署
  * 示例: true
* 键: autoAllowBashIfSandboxed
  * 描述: 当 sandboxed 时自动批准 bash 命令。默认：true
  * 示例: true
* 键: excludedCommands
  * 描述: 应在 sandbox 外运行的命令
  * 示例: ["git", "docker"]
* 键: allowUnsandboxedCommands
  * 描述: 允许命令通过 dangerouslyDisableSandbox 参数在 sandbox 外运行。当设置为 false 时，dangerouslyDisableSandbox 逃生舱口完全禁用，所有命令必须 sandboxed（或在 excludedCommands 中）。对于需要严格 sandboxing 的企业策略很有用。默认：true
  * 示例: false
* 键: filesystem.allowWrite
  * 描述: sandboxed 命令可以写入的额外路径。数组跨所有设置作用域合并：用户、项目和 managed 路径组合，不替换。也与 Edit(...) 允许权限规则中的路径合并。请参阅下面的路径前缀。
  * 示例: ["/tmp/build", "~/.kube"]
* 键: filesystem.denyWrite
  * 描述: sandboxed 命令无法写入的路径。数组跨所有设置作用域合并。也与 Edit(...) 拒绝权限规则中的路径合并。
  * 示例: ["/etc", "/usr/local/bin"]
* 键: filesystem.denyRead
  * 描述: sandboxed 命令无法读取的路径。数组跨所有设置作用域合并。也与 Read(...) 拒绝权限规则中的路径合并。
  * 示例: ["~/.aws/credentials"]
* 键: filesystem.allowRead
  * 描述: 在 denyRead 区域内重新允许读取的路径。优先于 denyRead。数组跨所有设置作用域合并。使用此创建仅工作区读取访问模式。
  * 示例: ["."]
* 键: filesystem.allowManagedReadPathsOnly
  * 描述: （仅 Managed 设置）仅尊重来自 managed 设置的 filesystem.allowRead 路径。denyRead 仍从所有源合并。默认：false
  * 示例: true
* 键: network.allowUnixSockets
  * 描述: sandbox 中可访问的 Unix socket 路径（用于 SSH agents 等）
  * 示例: ["~/.ssh/agent-socket"]
* 键: network.allowAllUnixSockets
  * 描述: 允许 sandbox 中的所有 Unix socket 连接。默认：false
  * 示例: true
* 键: network.allowLocalBinding
  * 描述: 允许绑定到 localhost 端口（仅 macOS）。默认：false
  * 示例: true
* 键: network.allowedDomains
  * 描述: 允许出站网络流量的域数组。支持通配符（例如 *.example.com）。
  * 示例: ["github.com", "*.npmjs.org"]
* 键: network.allowManagedDomainsOnly
  * 描述: （仅 Managed 设置）仅尊重来自 managed 设置的 allowedDomains 和 WebFetch(domain:...) 允许规则。来自用户、项目和本地设置的域被忽略。非允许的域自动被阻止，不提示用户。拒绝的域仍从所有源受尊重。默认：false
  * 示例: true
* 键: network.httpProxyPort
  * 描述: 如果您想自带代理，使用的 HTTP 代理端口。如果未指定，Claude 将运行自己的代理。
  * 示例: 8080
* 键: network.socksProxyPort
  * 描述: 如果您想自带代理，使用的 SOCKS5 代理端口。如果未指定，Claude 将运行自己的代理。
  * 示例: 8081
* 键: enableWeakerNestedSandbox
  * 描述: 为无特权 Docker 环境启用较弱的 sandbox（仅 Linux 和 WSL2）。降低安全性。 默认：false
  * 示例: true
* 键: enableWeakerNetworkIsolation
  * 描述: （仅 macOS）允许在 sandbox 中访问系统 TLS 信任服务（com.apple.trustd.agent）。对于 Go 基础工具（如 gh、gcloud 和 terraform）在使用 httpProxyPort 与 MITM 代理和自定义 CA 时验证 TLS 证书是必需的。通过打开潜在的数据泄露路径降低安全性。默认：false
  * 示例: true


#### Sandbox 路径前缀

`filesystem.allowWrite`、`filesystem.denyWrite`、`filesystem.denyRead` 和 `filesystem.allowRead` 中的路径支持这些前缀：



* 前缀: /
  * 含义: 从文件系统根目录的绝对路径
  * 示例: /tmp/build 保持 /tmp/build
* 前缀: ~/
  * 含义: 相对于主目录
  * 示例: ~/.kube 变为 $HOME/.kube
* 前缀: ./ 或无前缀
  * 含义: 相对于项目设置的��目根目录，或相对于用户设置的 ~/.claude
  * 示例: ./output 在 .claude/settings.json 中解析为 <project-root>/output


较旧的 `//path` 前缀用于绝对路径仍然有效。如果您之前使用单斜杠 `/path` 期望项目相对解析，请切换到 `./path`。此语法与[读取和编辑权限规则](about:/docs/zh-CN/permissions#read-and-edit)不同，后者使用 `//path` 用于绝对和 `/path` 用于项目相对。Sandbox 文件系统路径使用标准约定：`/tmp/build` 是绝对路径。 **配置示例：**

```
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["docker"],
    "filesystem": {
      "allowWrite": ["/tmp/build", "~/.kube"],
      "denyRead": ["~/.aws/credentials"]
    },
    "network": {
      "allowedDomains": ["github.com", "*.npmjs.org", "registry.yarnpkg.com"],
      "allowUnixSockets": [
        "/var/run/docker.sock"
      ],
      "allowLocalBinding": true
    }
  }
}

```


**文件系统和网络限制**可以通过两种合并在一起的方式配置：

*   **`sandbox.filesystem` 设置**（如上所示）：在 OS 级 sandbox 边界处控制路径。这些限制适用于所有子进程命令（例如 `kubectl`、`terraform`、`npm`），而不仅仅是 Claude 的文件工具。
*   **权限规则**：使用 `Edit` 允许/拒绝规则控制 Claude 的文件工具访问，`Read` 拒绝规则阻止读取，`WebFetch` 允许/拒绝规则控制网络域。这些规则中的路径也合并到 sandbox 配置中。

### 归属设置

Claude Code 为 git 提交和拉取请求添加归属。这些分别配置：

*   提交默认使用 [git trailers](https://git-scm.com/docs/git-interpret-trailers)（如 `Co-Authored-By`），可以自定义或禁用
*   拉取请求描述是纯文本


|键     |描述                                |
|------|----------------------------------|
|commit|git 提交的归属，包括任何 trailers。空字符串隐藏提交归属|
|pr    |拉取请求描述的归属。空字符串隐藏拉取请求归属            |


**默认提交归属：**

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude Sonnet 4.6 <[email protected]>

```


**默认拉取请求归属：**

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

```


**示例：**

```
{
  "attribution": {
    "commit": "Generated with AI\n\nCo-Authored-By: AI <[email protected]>",
    "pr": ""
  }
}

```


### 文件建议设置

为 `@` 文件路径自动完成配置自定义命令。内置文件建议使用快速文件系统遍历，但大型 monorepos 可能受益于项目特定的索引，例如预构建的文件索引或自定义工具。

```
{
  "fileSuggestion": {
    "type": "command",
    "command": "~/.claude/file-suggestion.sh"
  }
}

```


该命令使用与 [hooks](https://code.claude.com/docs/zh-CN/hooks) 相同的环境变量运行，包括 `CLAUDE_PROJECT_DIR`。它通过 stdin 接收包含 `query` 字段的 JSON：

将换行符分隔的文件路径输出到 stdout（当前限制为 15）：

```
src/components/Button.tsx
src/components/Modal.tsx
src/components/Form.tsx

```


**示例：**

```
#!/bin/bash
query=$(cat | jq -r '.query')
your-repo-file-index --query "$query" | head -20

```


### Hook 配置

这些设置控制允许运行哪些 hooks 以及 HTTP hooks 可以访问什么。`allowManagedHooksOnly` 设置只能在 [managed 设置](#settings-files)中配置。URL 和环境变量允许列表可以在任何设置级别设置并跨源合并。 **当 `allowManagedHooksOnly` 为 `true` 时的行为：**

*   加载 Managed hooks 和 SDK hooks
*   用户 hooks、项目 hooks 和插件 hooks 被阻止

**限制 HTTP hook URL：** 限制 HTTP hooks 可以针对的 URL。支持 `*` 作为匹配的通配符。定义数组后，针对不匹配 URL 的 HTTP hooks 被静默阻止。

```
{
  "allowedHttpHookUrls": ["https://hooks.example.com/*", "http://localhost:*"]
}

```


**限制 HTTP hook 环境变量：** 限制 HTTP hooks 可以插入到标头值中的环境变量名称。每个 hook 的有效 `allowedEnvVars` 是其自己列表与此设置的交集。

```
{
  "httpHookAllowedEnvVars": ["MY_TOKEN", "HOOK_SECRET"]
}

```


### 设置优先级

设置按优先级顺序应用。从最高到最低：

1.  **Managed 设置**（[服务器管理](https://code.claude.com/docs/zh-CN/server-managed-settings)、[MDM/OS 级别策略](#configuration-scopes) 或 [managed 设置](about:/docs/zh-CN/settings#settings-files)）
    *   由 IT 通过服务器交付、MDM 配置文件、注册表策略或 managed 设置文件部署的策略
    *   无法被任何其他级别覆盖，包括命令行参数
    *   在 managed 层内，优先级为：server-managed > MDM/OS 级别策略 > 基于文件（`managed-settings.d/*.json` + `managed-settings.json`）> HKCU 注册表（仅 Windows）。仅使用一个 managed 源；源不合并跨层。在基于文件的层内，放入文件和基础文件被合并在一起。
2.  **命令行参数**
    *   特定会话的临时覆盖
3.  **本地项目设置**（`.claude/settings.local.json`）
    *   个人项目特定设置
4.  **共享项目设置**（`.claude/settings.json`）
    *   源代码管理中的团队共享项目设置
5.  **用户设置**（`~/.claude/settings.json`）
    *   个人全局设置

此层次结构确保组织策略始终被强制执行，同时仍允许团队和个人自定义其体验。无论您从 CLI、[VS Code 扩展](https://code.claude.com/docs/zh-CN/vs-code) 还是 [JetBrains IDE](https://code.claude.com/docs/zh-CN/jetbrains) 运行 Claude Code，相同的优先级都适用。 例如，如果您的用户设置允许 `Bash(npm run *)`，但项目的共享设置拒绝它，则项目设置优先，命令被阻止。

### 验证活跃设置

在 Claude Code 中运行 `/status` 以查看哪些设置源处于活跃状态以及它们来自何处。输出显示每个配置层（managed、user、project）及其来源，例如 `Enterprise managed settings (remote)`、`Enterprise managed settings (plist)`、`Enterprise managed settings (HKLM)` 或 `Enterprise managed settings (file)`。如果设置文件包含错误，`/status` 会报告问题，以便您可以修复它。

### 配置系统的关键点

*   **内存文件（`CLAUDE.md`）**：包含 Claude 在启动时加载的说明和上下文
*   **设置文件（JSON）**：配置权限、环境变量和工具行为
*   **Skills**：可以使用 `/skill-name` 调用或由 Claude 自动加载的自定义提示
*   **MCP servers**：使用额外的工具和集成扩展 Claude Code
*   **优先级**：更高级别的配置（Managed）覆盖较低级别的配置（User/Project）
*   **继承**：设置被合并，更具体的设置添加到或覆盖更广泛的设置

### 系统提示

Claude Code 的内部系统提示未发布。要添加自定义说明，请使用 `CLAUDE.md` 文件或 `--append-system-prompt` 标志。

### 排除敏感文件

要防止 Claude Code 访问包含敏感信息（如 API 密钥、secrets 和环境文件）的文件，请在您的 `.claude/settings.json` 文件中使用 `permissions.deny` 设置：

```
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(./config/credentials.json)",
      "Read(./build)"
    ]
  }
}

```


这替代了已弃用的 `ignorePatterns` 配置。匹配这些模式的文件被排除在文件发现和搜索结果之外，这些文件上的读取操作被拒绝。

Subagent 配置
-----------

Claude Code 支持可在用户和项目级别配置的自定义 AI subagents。这些 subagents 存储为带有 YAML frontmatter 的 Markdown 文件：

*   **用户 subagents**：`~/.claude/agents/` - 在所有项目中可用
*   **项目 subagents**：`.claude/agents/` - 特定于您的项目，可与您的团队共享

Subagent 文件定义具有自定义提示和工具权限的专门 AI 助手。在 [subagents 文档](https://code.claude.com/docs/zh-CN/sub-agents)中了解有关创建和使用 subagents 的更多信息。

插件配置
----

Claude Code 支持一个插件系统，让您可以使用 skills、agents、hooks 和 MCP servers 扩展功能。插件通过市场分发，可以在用户和存储库级别配置。

### 插件设置

`settings.json` 中的插件相关设置：

```
{
  "enabledPlugins": {
    "formatter@acme-tools": true,
    "deployer@acme-tools": true,
    "analyzer@security-plugins": false
  },
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": "github",
      "repo": "acme-corp/claude-plugins"
    }
  }
}

```


#### `enabledPlugins`

控制启用哪些插件。格式：`"plugin-name@marketplace-name": true/false` **作用域**：

*   **用户设置**（`~/.claude/settings.json`）：个人插件偏好
*   **项目设置**（`.claude/settings.json`）：与团队共享的项目特定插件
*   **本地设置**（`.claude/settings.local.json`）：每台机器的覆盖（未提交）
*   **Managed 设置**（`managed-settings.json`）：组织范围的策略覆盖，在所有作用域中阻止安装并从市场隐藏插件

**示例**：

```
{
  "enabledPlugins": {
    "code-formatter@team-tools": true,
    "deployment-tools@team-tools": true,
    "experimental-features@personal": false
  }
}

```


定义应为存储库提供的额外市场。通常在存储库级别设置中使用，以确保团队成员有权访问所需的插件源。 **当存储库包含 `extraKnownMarketplaces` 时**：

1.  当他们信任文件夹时，团队成员被提示安装市场
2.  然后团队成员被提示从该市场安装插件
3.  用户可以跳过不需要的市场或插件（存储在用户设置中）
4.  安装尊重信任边界并需要明确同意

**示例**：

```
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": {
        "source": "github",
        "repo": "acme-corp/claude-plugins"
      }
    },
    "security-plugins": {
      "source": {
        "source": "git",
        "url": "https://git.example.com/security/plugins.git"
      }
    }
  }
}

```


**市场源类型**：

*   `github`：GitHub 存储库（使用 `repo`）
*   `git`：任何 git URL（使用 `url`）
*   `directory`：本地文件系统路径（使用 `path`，仅用于开发）
*   `hostPattern`：正则表达式模式以匹配市场主机（使用 `hostPattern`）
*   `settings`：直接在 settings.json 中声明的内联市场，无需单独的托管存储库（使用 `name` 和 `plugins`）

使用 `source: 'settings'` 声明一小组插件内联，无需设置托管市场存储库。此处列出的插件必须引用外部源，例如 GitHub 或 npm。您仍需要在 `enabledPlugins` 中单独启用每个插件。

```
{
  "extraKnownMarketplaces": {
    "team-tools": {
      "source": {
        "source": "settings",
        "name": "team-tools",
        "plugins": [
          {
            "name": "code-formatter",
            "source": {
              "source": "github",
              "repo": "acme-corp/code-formatter"
            }
          }
        ]
      }
    }
  }
}

```


#### `strictKnownMarketplaces`

**仅 Managed 设置**：控制用户允许添加哪些插件市场。此设置只能在 [managed 设置](about:/docs/zh-CN/settings#settings-files)中配置，为管理员提供对市场源的严格控制。 **Managed 设置文件位置**：

*   **macOS**：`/Library/Application Support/ClaudeCode/managed-settings.json`
*   **Linux 和 WSL**：`/etc/claude-code/managed-settings.json`
*   **Windows**：`C:\Program Files\ClaudeCode\managed-settings.json`

**关键特征**：

*   仅在 managed 设置（`managed-settings.json`）中可用
*   无法被用户或项目设置覆盖（最高优先级）
*   在网络/文件系统操作之前强制执行（被阻止的源永远不会执行）
*   对源规范使用精确匹配（包括 `ref`、`path` 用于 git 源），除了 `hostPattern`，它使用正则表达式匹配

**允许列表行为**：

*   `undefined`（默认）：无限制 - 用户可以添加任何市场
*   空数组 `[]`：完全锁定 - 用户无法添加任何新市场
*   源列表：用户只能添加与之完全匹配的市场

**所有支持的源类型**： 允许列表支持多种市场源类型。大多数源使用精确匹配，而 `hostPattern` 使用正则表达式匹配市场主机。

1.  **GitHub 存储库**：

```
{ "source": "github", "repo": "acme-corp/approved-plugins" }
{ "source": "github", "repo": "acme-corp/security-tools", "ref": "v2.0" }
{ "source": "github", "repo": "acme-corp/plugins", "ref": "main", "path": "marketplace" }

```


字段：`repo`（必需）、`ref`（可选：分支/标签/SHA）、`path`（可选：子目录）

2.  **Git 存储库**：

```
{ "source": "git", "url": "https://gitlab.example.com/tools/plugins.git" }
{ "source": "git", "url": "https://bitbucket.org/acme-corp/plugins.git", "ref": "production" }
{ "source": "git", "url": "ssh://[email protected]/plugins.git", "ref": "v3.1", "path": "approved" }

```


字段：`url`（必需）、`ref`（可选：分支/标签/SHA）、`path`（可选：子目录）

3.  **基于 URL 的市场**：

```
{ "source": "url", "url": "https://plugins.example.com/marketplace.json" }
{ "source": "url", "url": "https://cdn.example.com/marketplace.json", "headers": { "Authorization": "Bearer ${TOKEN}" } }

```


字段：`url`（必需）、`headers`（可选：用于身份验证访问的 HTTP 标头）

4.  **NPM 包**：

```
{ "source": "npm", "package": "@acme-corp/claude-plugins" }
{ "source": "npm", "package": "@acme-corp/approved-marketplace" }

```


字段：`package`（必需，支持作用域包）

5.  **文件路径**：

```
{ "source": "file", "path": "/usr/local/share/claude/acme-marketplace.json" }
{ "source": "file", "path": "/opt/acme-corp/plugins/marketplace.json" }

```


字段：`path`（必需：marketplace.json 文件的绝对路径）

6.  **目录路径**：

```
{ "source": "directory", "path": "/usr/local/share/claude/acme-plugins" }
{ "source": "directory", "path": "/opt/acme-corp/approved-marketplaces" }

```


字段：`path`（必需：包含 `.claude-plugin/marketplace.json` 的目录的绝对路径）

7.  **主机模式匹配**：

```
{ "source": "hostPattern", "hostPattern": "^github\\.example\\.com$" }
{ "source": "hostPattern", "hostPattern": "^gitlab\\.internal\\.example\\.com$" }

```


字段：`hostPattern`（必需：与市场主机匹配的正则表达式模式） 当您想允许来自特定主机的所有市场而不枚举每个存储库时，使用主机模式匹配。这对于具有内部 GitHub Enterprise 或 GitLab 服���器的组织很有用，开发人员在其中创建自己的市场。 按源类型的主机提取：

*   `github`：始终与 `github.com` 匹配
*   `git`：从 URL 提取主机名（支持 HTTPS 和 SSH 格式）
*   `url`：从 URL 提取主机名
*   `npm`、`file`、`directory`：不支持主机模式匹配

**配置示例**： 示例：仅允许特定市场：

```
{
  "strictKnownMarketplaces": [
    {
      "source": "github",
      "repo": "acme-corp/approved-plugins"
    },
    {
      "source": "github",
      "repo": "acme-corp/security-tools",
      "ref": "v2.0"
    },
    {
      "source": "url",
      "url": "https://plugins.example.com/marketplace.json"
    },
    {
      "source": "npm",
      "package": "@acme-corp/compliance-plugins"
    }
  ]
}

```


示例 - 禁用所有市场添加：

```
{
  "strictKnownMarketplaces": []
}

```


示例：允许来自内部 git 服务器的所有市场：

```
{
  "strictKnownMarketplaces": [
    {
      "source": "hostPattern",
      "hostPattern": "^github\\.example\\.com$"
    }
  ]
}

```


**精确匹配要求**： 市场源必须**精确**匹配才能允许用户的添加。对于基于 git 的源（`github` 和 `git`），这包括所有可选字段：

*   `repo` 或 `url` 必须精确匹配
*   `ref` 字段必须精确匹配（或两者都未定义）
*   `path` 字段必须精确匹配（或两者都未定义）

**不匹配**的源示例：

```
// 这些是不同的源：
{ "source": "github", "repo": "acme-corp/plugins" }
{ "source": "github", "repo": "acme-corp/plugins", "ref": "main" }

// 这些也是不同的：
{ "source": "github", "repo": "acme-corp/plugins", "path": "marketplace" }
{ "source": "github", "repo": "acme-corp/plugins" }

```


**与 `extraKnownMarketplaces` 的比较**：


|方面    |strictKnownMarketplaces|extraKnownMarketplaces|
|------|-----------------------|----------------------|
|目的    |组织策略强制执行               |团队便利                  |
|设置文件  |仅 managed-settings.json|任何设置文件                |
|行为    |阻止非允许列表的添加             |自动安装缺失的市场             |
|何时强制执行|在网络/文件系统操作之前           |在用户信任提示之后             |
|可以被覆盖 |否（最高优先级）               |是（由更高优先级设置）           |
|源格式   |直接源对象                  |具有嵌套源的命名市场            |
|用例    |合规、安全限制                |入职、标准化                |


**格式差异**： `strictKnownMarketplaces` 使用直接源对象：

```
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "acme-corp/plugins" }
  ]
}

```


`extraKnownMarketplaces` 需要命名市场：

```
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "github", "repo": "acme-corp/plugins" }
    }
  }
}

```


**同时使用两者**： `strictKnownMarketplaces` 是一个策略门：它控制用户可能添加什么，但不注册任何市场。要同时限制和为所有用户预注册市场，请在 `managed-settings.json` 中设置两者：

```
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "acme-corp/plugins" }
  ],
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "github", "repo": "acme-corp/plugins" }
    }
  }
}

```


仅设置 `strictKnownMarketplaces` 时，用户仍可以通过 `/plugin marketplace add` 手动添加允许的市场，但它不会自动可用。 **重要说明**：

*   限制在任何网络请求或文件系统操作之前检查
*   被阻止时，用户看到清晰的错误消息，指示源被 managed 策略���止
*   限制仅适用于添加新市场；以前安装的市场保持可访问
*   Managed 设置具有最高优先级，无法被覆盖

请参阅 [Managed 市场限制](about:/docs/zh-CN/plugin-marketplaces#managed-marketplace-restrictions)了解面向用户的文档。

### 管理插件

使用 `/plugin` 命令以交互方式管理插件：

*   浏览市场中的可用插件
*   安装/卸载插件
*   启用/禁用插件
*   查看插件详情（提供的命令、agents、hooks）
*   添加/删除市场

在[插件文档](https://code.claude.com/docs/zh-CN/plugins)中了解有关插件系统的更多信息。

环境变量
----

环境变量让您可以控制 Claude Code 行为而无需编辑设置文件。任何变量也可以在 [`settings.json`](#available-settings) 中的 `env` 键下配置，以将其应用于每个会话或将其推出到您的团队。 请参阅[环境变量参考](https://code.claude.com/docs/zh-CN/env-vars)了解完整列表。

Claude Code 可以访问一组用于读取、编辑、搜索、运行命令和编排 subagents 的工具。工具名称是您在权限规则和 hook 匹配器中使用的确切字符串。 请参阅[工具参考](https://code.claude.com/docs/zh-CN/tools-reference)了解完整列表和 Bash 工具行为详情。

另请参阅
----

*   [权限](https://code.claude.com/docs/zh-CN/permissions)：权限系统、规则语法、工具特定模式和 managed 策略
*   [身份验证](https://code.claude.com/docs/zh-CN/authentication)：设置用户对 Claude Code 的访问
*   [故障排除](https://code.claude.com/docs/zh-CN/troubleshooting)：常见配置问题的解决方案