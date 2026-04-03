# 配置权限 - Claude Code Docs
Claude Code 支持细粒度权限，因此您可以精确指定代理允许执行的操作和不允许执行的操作。权限设置可以检入版本控制并分发给组织中的所有开发人员，也可以由个别开发人员自定义。

权限系统
----

Claude Code 使用分层权限系统来平衡功能和安全性：


|工具类型   |示例           |需要批准|”是，不再询问”行为   |
|-------|-------------|----|-------------|
|只读     |文件读取、Grep    |否   |不适用          |
|Bash 命令|Shell 执行     |是   |每个项目目录和命令永久有效|
|文件修改   |Edit/Write 文件|是   |直到会话结束       |


管理权限
----

您可以使用 `/permissions` 查看和管理 Claude Code 的工具权限。此 UI 列出所有权限规则和它们来自的 settings.json 文件。

*   **Allow** 规则让 Claude Code 使用指定的工具而无需手动批准。
*   **Ask** 规则在 Claude Code 尝试使用指定工具时提示确认。
*   **Deny** 规则防止 Claude Code 使用指定的工具。

规则按顺序评估：**deny -> ask -> allow**。第一个匹配的规则获胜，因此 deny 规则始终优先。

权限模式
----

Claude Code 支持多种权限模式来控制工具的批准方式。请参阅[权限模式](https://code.claude.com/docs/zh-CN/permission-modes)了解何时使用每种模式。在您的[设置文件](about:/docs/zh-CN/settings#settings-files)中设置 `defaultMode`：


|模式               |描述                                                 |
|-----------------|---------------------------------------------------|
|default          |标准行为：在首次使用每个工具时提示权限                                |
|acceptEdits      |自动接受会话的文件编辑权限，受保护目录的写入除外                           |
|plan             |Plan Mode：Claude 可以分析但不能修改文件或执行命令                  |
|auto             |自动批准工具调用，并进行后台安全检查以验证操作与您的请求一致。目前处于研究预览阶段          |
|dontAsk          |自动拒绝工具，除非通过 /permissions 或 permissions.allow 规则预先批准|
|bypassPermissions|跳过权限提示，除了对受保护目录的写入（请参见下面的警告）                       |


为了防止使用 `bypassPermissions` 或 `auto` 模式，在任何[设置文件](about:/docs/zh-CN/settings#settings-files)中将 `permissions.disableBypassPermissionsMode` 或 `permissions.disableAutoMode` 设置为 `"disable"`。这些在[托管设置](#managed-settings)中最有用，因为它们无法被覆盖。

权限规则语法
------

权限规则遵循格式 `Tool` 或 `Tool(specifier)`。

### 匹配工具的所有使用

要匹配工具的所有使用，只需使用工具名称而不带括号：


|规则      |效果          |
|--------|------------|
|Bash    |匹配所有 Bash 命令|
|WebFetch|匹配所有网络获取请求  |
|Read    |匹配所有文件读取    |


`Bash(*)` 等同于 `Bash` 并匹配所有 Bash 命令。

### 使用说明符进行细粒度控制

在括号中添加说明符以匹配特定的工具使用：


|规则                          |效果                   |
|----------------------------|---------------------|
|Bash(npm run build)         |匹配确切的命令 npm run build|
|Read(./.env)                |匹配读取当前目录中的 .env 文件   |
|WebFetch(domain:example.com)|匹配对 example.com 的获取请求|


### 通配符模式

Bash 规则支持带有 `*` 的 glob 模式。通配符可以出现在命令中的任何位置。此配置允许 npm 和 git commit 命令，同时阻止 git push：

```
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(git commit *)",
      "Bash(git * main)",
      "Bash(* --version)",
      "Bash(* --help *)"
    ],
    "deny": [
      "Bash(git push *)"
    ]
  }
}

```


`*` 前的空格很重要：`Bash(ls *)` 匹配 `ls -la` 但不匹配 `lsof`，而 `Bash(ls*)` 匹配两者。旧版 `:*` 后缀语法等同于 `*` 但已弃用。

工具特定的权限规则
---------

### Bash

Bash 权限规则支持带有 `*` 的通配符匹配。通配符可以出现在命令中的任何位置，包括开头、中间或结尾：

*   `Bash(npm run build)` 匹配确切的 Bash 命令 `npm run build`
*   `Bash(npm run test *)` 匹配以 `npm run test` 开头的 Bash 命令
*   `Bash(npm *)` 匹配任何以 `npm` 开头的命令
*   `Bash(* install)` 匹配任何以 `install` 结尾的命令
*   `Bash(git * main)` 匹配 `git checkout main`、`git merge main` 等命令

当 `*` 出现在末尾且前面有空格时（如 `Bash(ls *)`），它强制执行单词边界，要求前缀后跟空格或字符串结尾。例如，`Bash(ls *)` 匹配 `ls -la` 但不匹配 `lsof`。相比之下，`Bash(ls*)` 没有空格匹配 `ls -la` 和 `lsof` 两者，因为没有单词边界约束。

当您使用”是，不再询问”批准复合命令时，Claude Code 会为需要批准的每个子命令保存一个单独的规则，而不是为完整的复合字符串保存单个规则。例如，批准 `git status && npm test` 会为 `npm test` 保存一个规则，因此将来的 `npm test` 调用被识别，无论 `&&` 前面是什么。诸如 `cd` 进入子目录之类的子命令会为该路径生成自己的 Read 规则。单个复合命令最多可能保存 5 个规则。

### Read 和 Edit

`Edit` 规则适用于所有编辑文件的内置工具。Claude 尽力将 `Read` 规则应用于所有读取文件的内置工具，如 Grep 和 Glob。

Read 和 Edit 规则都遵循 [gitignore](https://git-scm.com/docs/gitignore) 规范，具有四种不同的模式类型：


|模式           |含义            |示例                            |匹配                          |
|-------------|--------------|------------------------------|----------------------------|
|//path       |来自文件系统根目录的绝对路径|Read(//Users/alice/secrets/**)|/Users/alice/secrets/**     |
|~/path       |来自主目录的路径      |Read(~/Documents/*.pdf)       |/Users/alice/Documents/*.pdf|
|/path        |相对于项目根目录的路径   |Edit(/src/**/*.ts)            |<project root>/src/**/*.ts  |
|path 或 ./path|相对于当前目录的路径    |Read(*.env)                   |<cwd>/*.env                 |


在 Windows 上，路径在匹配前被规范化为 POSIX 形式。`C:\Users\alice` 变成 `/c/Users/alice`，因此使用 `//c/**/.env` 来匹配该驱动器上的 `.env` 文件。要在所有驱动器上匹配，使用 `//**/.env`。 示例：

*   `Edit(/docs/**)`：编辑 `<project>/docs/` 中的文件（不是 `/docs/` 也不是 `<project>/.claude/docs/`）
*   `Read(~/.zshrc)`：读取您主目录的 `.zshrc`
*   `Edit(//tmp/scratch.txt)`：编辑绝对路径 `/tmp/scratch.txt`
*   `Read(src/**)`：从 `<current-directory>/src/` 读取

### WebFetch

*   `WebFetch(domain:example.com)` 匹配对 example.com 的获取请求

### MCP

*   `mcp__puppeteer` 匹配由 `puppeteer` 服务器提供的任何工具（在 Claude Code 中配置的名称）
*   `mcp__puppeteer__*` 通配符语法，也匹配来自 `puppeteer` 服务器的所有工具
*   `mcp__puppeteer__puppeteer_navigate` 匹配由 `puppeteer` 服务器提供的 `puppeteer_navigate` 工具

### Agent（subagents）

使用 `Agent(AgentName)` 规则来控制 Claude 可以使用哪些[子代理](https://code.claude.com/docs/zh-CN/sub-agents)：

*   `Agent(Explore)` 匹配 Explore 子代理
*   `Agent(Plan)` 匹配 Plan 子代理
*   `Agent(my-custom-agent)` 匹配名为 `my-custom-agent` 的自定义子代理

将这些规则添加到您的设置中的 `deny` 数组，或使用 `--disallowedTools` CLI 标志来禁用特定代理。要禁用 Explore 代理：

```
{
  "permissions": {
    "deny": ["Agent(Explore)"]
  }
}

```


使用 hooks 扩展权限
-------------

[Claude Code hooks](https://code.claude.com/docs/zh-CN/hooks-guide)提供了一种方法来注册自定义 shell 命令以在运行时执行权限评估。当 Claude Code 进行工具调用时，PreToolUse hooks 在权限提示之前运行。hook 输出可以拒绝工具调用、强制提示或跳过提示以让调用继续。 跳过提示不会绕过权限规则。Deny 和 ask 规则在 hook 返回 `"allow"` 后仍然被评估，因此匹配的 deny 规则仍然会阻止调用。这保留了[管理权限](#manage-permissions)中描述的 deny 优先级，包括在托管设置中设置的 deny 规则。 阻止 hook 也优先于 allow 规则。以退出代码 2 退出的 hook 在权限规则被评估之前停止工具调用，因此即使 allow 规则会让调用继续，阻止也适用。要运行所有 Bash 命令而无需提示，除了您想要阻止的少数几个，将 `"Bash"` 添加到您的 allow 列表，并注册一个 PreToolUse hook 来拒绝那些特定命令。请参见[阻止对受保护文件的编辑](about:/docs/zh-CN/hooks-guide#block-edits-to-protected-files)以获取您可以调整的 hook 脚本。

工作目录
----

默认情况下，Claude 可以访问启动它的目录中的文件。您可以扩展此访问：

*   **启动期间**：使用 `--add-dir <path>` CLI 参数
*   **会话��间**：使用 `/add-dir` 命令
*   **持久配置**：添加到[设置文件](about:/docs/zh-CN/settings#settings-files)中的 `additionalDirectories`

其他目录中的文件遵循与原始工作目录相同的权限规则：它们变为可读的而无需提示，文件编辑权限遵循当前权限模式。

### 其他目录授予文件访问权限，而不是配置

添加目录扩展 Claude 可以读取和编辑文件的位置。它不会使该目录成为完整的配置根目录：大多数 `.claude/` 配置不是从其他目录发现的，尽管有几种类型作为例外被加载。 以下配置类型从 `--add-dir` 目录加载：


|配置                          |从 --add-dir 加载                                       |
|----------------------------|-----------------------------------------------------|
|.claude/skills/ 中的 Skills   |是，带有实时重新加载                                           |
|.claude/settings.json 中的插件设置|仅 enabledPlugins 和 extraKnownMarketplaces            |
|CLAUDE.md 文件和 .claude/rules/|仅当设置 CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 时|


其他所有内容，包括子代理、命令、输出样式、hooks 和其他设置，仅从当前工作目录及其父目录、您在 `~/.claude/` 的用户目录和托管设置中发现。要在项目间共享该配置，请使用以下方法之一：

*   **用户级配置**：将文件放在 `~/.claude/agents/`、`~/.claude/output-styles/` 或 `~/.claude/settings.json` 中，使其在每个项目中可用
*   **插件**：将配置打包并分发为[插件](https://code.claude.com/docs/zh-CN/plugins)，团队可以安装
*   **从配置目录启动**：从包含您想要的 `.claude/` 配置的目录运行 Claude Code

权限如何与沙箱交互
---------

权限和[沙箱](https://code.claude.com/docs/zh-CN/sandboxing)是互补的安全层：

*   **权限**控制 Claude Code 可以使用哪些工具以及它可以访问哪些文件或域。它们适用于所有工具（Bash、Read、Edit、WebFetch、MCP 和其他）。
*   **沙箱**提供 OS 级别的强制执行，限制 Bash 工具的文件系统和网络访问。它仅适用于 Bash 命令及其子进程。

使用两者进行深度防御：

*   权限 deny 规则阻止 Claude 甚至尝试访问受限资源
*   沙箱限制防止 Bash 命令到达定义边界之外的资源，即使提示注入绕过 Claude 的决策制定
*   沙箱中的文件系统限制使用 Read 和 Edit deny 规则，而不是单独的沙箱配置
*   网络限制结合 WebFetch 权限规则与沙箱的 `allowedDomains` 列表

托管设置
----

对于需要对 Claude Code 配置进行集中控制的组织，管理员可以部署无法被用户或项目设置覆盖的托管设置。这些策略设置遵循与常规设置文件相同的格式，可以通过 MDM/OS 级别策略、托管设置文件或[服务器托管设置](https://code.claude.com/docs/zh-CN/server-managed-settings)传递。有关传递机制和文件位置，请参见[设置文件](about:/docs/zh-CN/settings#settings-files)。

### 仅托管设置

以下设置仅在托管设置中有效。将它们放在用户或项目设置文件中无效。



* 设置: allowedChannelPlugins
  * 描述: 可能推送消息的频道插件的允许列表。设置时替换默认 Anthropic 允许列表。需要 channelsEnabled: true。请参见限制哪些频道插件可以运行
* 设置: allowManagedHooksOnly
  * 描述: 当为 true 时，防止加载用户、项目和插件 hooks。仅允许托管 hooks 和 SDK hooks
* 设置: allowManagedMcpServersOnly
  * 描述: 当为 true 时，仅尊重来自托管设置的 allowedMcpServers。deniedMcpServers 仍然从所有来源合并。请参见托管 MCP 配置
* 设置: allowManagedPermissionRulesOnly
  * 描述: 当为 true 时，防止用户和项目设置定义 allow、ask 或 deny 权限规则。仅应用托管设置中的规则
* 设置: blockedMarketplaces
  * 描述: 市场来源的黑名单。在下载前检查被阻止的来源，因此它们永远不会接触文件系统。请参见托管市场限制
* 设置: channelsEnabled
  * 描述: 允许 Team 和 Enterprise 用户使用频道。未设置或 false 会阻止频道消息传递，无论用户传递什么给 --channels
* 设置: pluginTrustMessage
  * 描述: 自定义消息，附加到安装前显示的插件信任警告
* 设置: sandbox.filesystem.allowManagedReadPathsOnly
  * 描述: 当为 true 时，仅尊重来自托管设置的 filesystem.allowRead 路径。denyRead 仍然从所有来源合并
* 设置: sandbox.network.allowManagedDomainsOnly
  * 描述: 当为 true 时，仅尊重来自托管设置的 allowedDomains 和 WebFetch(domain:...) allow 规则。非允许的域被自动阻止，不提示用户。被拒绝的域仍然从所有来源合并
* 设置: strictKnownMarketplaces
  * 描述: 控制用户可以添加哪些插件市场。请参见托管市场限制


`disableBypassPermissionsMode` 通常放在托管设置中以强制执行组织策略，但它可以从任何范围工作。用户可以在自己的设置中设置它以将自己锁定在绕过模式之外。

审查自动模式拒绝
--------

当[自动模式](about:/docs/zh-CN/permission-modes#eliminate-prompts-with-auto-mode)拒绝工具调用时，会出现通知，被拒绝的操作被记录在 `/permissions` 下的”最近拒绝”���项卡中。在被拒绝的操作上按 `r` 将其标记为重试：当您退出对话框时，Claude Code 发送一条消息告诉模型它可能重试该工具调用并恢复对话。 要以编程方式对拒绝做出反应，请使用 [`PermissionDenied` hook](about:/docs/zh-CN/hooks#permissiondenied)。

配置自动模式分类器
---------

[自动模式](about:/docs/zh-CN/permission-modes#eliminate-prompts-with-auto-mode)使用分类器模型来决定每个操作是否可以安全运行而无需提示。开箱即用，它仅信任工作目录和（如果存在）当前存储库的远程。诸如推送到您公司的源代码控制组织或写入团队云存储桶之类的操作将被阻止为潜在的数据泄露。`autoMode` 设置块让您告诉分类器您的组织信任哪些基础设施。 分类器从用户设置、`.claude/settings.local.json` 和托管设置中读取 `autoMode`。它不从 `.claude/settings.json` 中的共享项目设置中读取，因为已检入的存储库可能会注入自己的 allow 规则。


|范围         |文件                         |用于                       |
|-----------|---------------------------|-------------------------|
|一个开发人员     |~/.claude/settings.json    |个人信任的基础设施                |
|一个项目，一个开发人员|.claude/settings.local.json|每个项目的信任的存储桶或服务，gitignored|
|组织范围       |托管设置                       |为所有开发人员强制执行的信任基础设施       |


来自每个范围的条目被合并。开发人员可以使用个人条目扩展 `environment`、`allow` 和 `soft_deny`，但无法删除托管设置提供的条目。因为 allow 规则在分类器内充当阻止规则的例外，开发人员添加的 `allow` 条目可以覆盖组织 `soft_deny` 条目：组合是加法的，不是硬策略边界。如果您需要开发人员无法绕过的规则，请���用托管设置中的 `permissions.deny`，它在分类器被咨询之前阻止操作。

### 定义信任的基础设施

对于大多数组织，`autoMode.environment` 是您需要设置的唯一字段。它告诉分类器哪些存储库、存储桶和域是信任的，而不触及内置的阻止和 allow 规则。分类器使用 `environment` 来决定”外部”的含义：任何未列出的目标都是潜在的泄露目标。

```
{
  "autoMode": {
    "environment": [
      "Source control: github.example.com/acme-corp and all repos under it",
      "Trusted cloud buckets: s3://acme-build-artifacts, gs://acme-ml-datasets",
      "Trusted internal domains: *.corp.example.com, api.internal.example.com",
      "Key internal services: Jenkins at ci.example.com, Artifactory at artifacts.example.com"
    ]
  }
}

```


条目是散文，不是正则表达式或工具模式。分类器将它们作为自然语言规则读取。按照您向新工程师描述基础设施的方式编写它们。彻底的环境部分涵盖：

*   **组织**：您的公司名称以及 Claude Code 主要用于什么，如软件开发、基础设施自动化或数据工程
*   **源代码控制**：您的开发人员推送到的每个 GitHub、GitLab 或 Bitbucket 组织
*   **云提供商和信任的存储桶**：Claude 应该能够读取和写入的存储桶名称或前缀
*   **信任的内部域**：您网络内的 API、仪表板和服务的主机名，如 `*.internal.example.com`
*   **关键内部服务**：CI、工件注册表、内部包索引、事件工具
*   **其他上下文**：受管制行业的约束、多租户基础设施或影响分类器应将什么视为风险的合规要求

一个有用的起始模板：填入括号中的字段并删除任何不适用的行：

```
{
  "autoMode": {
    "environment": [
      "Organization: {COMPANY_NAME}. Primary use: {PRIMARY_USE_CASE, e.g. software development, infrastructure automation}",
      "Source control: {SOURCE_CONTROL, e.g. GitHub org github.example.com/acme-corp}",
      "Cloud provider(s): {CLOUD_PROVIDERS, e.g. AWS, GCP, Azure}",
      "Trusted cloud buckets: {TRUSTED_BUCKETS, e.g. s3://acme-builds, gs://acme-datasets}",
      "Trusted internal domains: {TRUSTED_DOMAINS, e.g. *.internal.example.com, api.example.com}",
      "Key internal services: {SERVICES, e.g. Jenkins at ci.example.com, Artifactory at artifacts.example.com}",
      "Additional context: {EXTRA, e.g. regulated industry, multi-tenant infrastructure, compliance requirements}"
    ]
  }
}

```


您提供的上下文越具体，分类器就越能区分常规内部操作和泄露尝试。 您不需要一次性填写所有内容。合理的推出：从默认值开始，添加您的源代码控制组织和关键内部服务，这解决了最常见的误报，如推送到您自己的存储库。接下来添加信任的域和云存储桶。当阻止出现时填写其余部分。

### 覆盖阻止和 allow 规则

两个额外的字段让您替换分类器的内置规则列表：`autoMode.soft_deny` 控制被阻止的内容，`autoMode.allow` 控制哪些例外适用。每个都是散文描述的数组，作为自然语言规则读取。 在分类器内，优先级是：`soft_deny` 规则首先阻止，然后 `allow` 规则作为例外覆盖，然后显式用户意图覆盖两者。如果用户的消息直接且具体地描述 Claude 即将采取的确切操作，分类器允许它，即使 `soft_deny` 规则匹配。一般请求不计数：要求 Claude”清理存储库”不授权强制推送，但要求 Claude”强制推送此分支”则授权。 要放松：当默认值阻止您的管道已通过 PR 审查、CI 或暂存环境保护的内容时，从 `soft_deny` 中删除规则，或当分类器重复标记默认例外不涵盖的常规模式时添加到 `allow`。要收紧：添加到 `soft_deny` 以应对您的环境特有的风险，默认值遗漏，或从 `allow` 中删除以对阻止规则保持默认例外。在所有情况下，运行 `claude auto-mode defaults` 以获取完整的默认列表，然后复制和编辑：永远不要从空列表开始。

```
{
  "autoMode": {
    "environment": [
      "Source control: github.example.com/acme-corp and all repos under it"
    ],
    "allow": [
      "Deploying to the staging namespace is allowed: staging is isolated from production and resets nightly",
      "Writing to s3://acme-scratch/ is allowed: ephemeral bucket with a 7-day lifecycle policy"
    ],
    "soft_deny": [
      "Never run database migrations outside the migrations CLI, even against dev databases",
      "Never modify files under infra/terraform/prod/: production infrastructure changes go through the review workflow",
      "...copy full default soft_deny list here first, then add your rules..."
    ]
  }
}

```


三个部分被独立评估，因此仅设置 `environment` 保留默认的 `allow` 和 `soft_deny` 列表完整。

### 检查默认值和您的有效配置

因为设置 `allow` 或 `soft_deny` 替换默认值，通过复制完整的默认列表开始任何自定义。三个 CLI 子命令帮助您检查和验证：

```
claude auto-mode defaults  # the built-in environment, allow, and soft_deny rules
claude auto-mode config    # what the classifier actually uses: your settings where set, defaults otherwise
claude auto-mode critique  # get AI feedback on your custom allow and soft_deny rules

```


将 `claude auto-mode defaults` 的输出保存到文件，编辑列表以匹配您的策略，并将结果粘贴到您的设置文件中。保存后，运行 `claude auto-mode config` 以确认有效规则是您期望的。如果您编写了自定义规则，`claude auto-mode critique` 审查它们并标记模糊、冗余或可能导致误报的条目。

设置优先级
-----

权限规则遵循与所有其他 Claude Code 设置相同的[设置优先级](about:/docs/zh-CN/settings#settings-precedence)：

1.  **托管设置**：无法被任何其他级别覆盖，包括命令行参数
2.  **命令行参数**：临时会话覆盖
3.  **本地项目设置**（`.claude/settings.local.json`）
4.  **共享项目设置**（`.claude/settings.json`）
5.  **用户设置**（`~/.claude/settings.json`）

如果工具在任何级别被拒绝，没有其他级别可以允许它。例如，托管设置 deny 无法被 `--allowedTools` 覆盖，`--disallowedTools` 可以添加超出托管设置定义的限制。 如果权限在用户设置中被允许但在项目设置中被拒绝，项目设置优先，权限被阻止。

示例配置
----

此[存储库](https://github.com/anthropics/claude-code/tree/main/examples/settings)包括常见部署场景的启动设置配置。将这些用作起点并根据您的需要调整它们。

另请参见
----

*   [Settings](https://code.claude.com/docs/zh-CN/settings)：完整的配置参考，包括权限设置表
*   [Sandboxing](https://code.claude.com/docs/zh-CN/sandboxing)：Bash 命令的 OS 级文件系统和网络隔离
*   [Authentication](https://code.claude.com/docs/zh-CN/authentication)：设置用户对 Claude Code 的访问
*   [Security](https://code.claude.com/docs/zh-CN/security)：安全保障和最佳实践
*   [Hooks](https://code.claude.com/docs/zh-CN/hooks-guide)：自动化工作流并扩展权限评估