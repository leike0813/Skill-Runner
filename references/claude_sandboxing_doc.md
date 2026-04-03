# Sandboxing - Claude Code Docs
概述
--

Claude Code 具有原生沙箱功能，为代理执行提供更安全的环境，同时减少了对持续权限提示的需求。Claude Code 不是要求对每个 bash 命令进行权限批准，而是预先创建定义的边界，使 Claude Code 能够以降低的风险更自由地工作。 沙箱 bash 工具使用操作系统级原语来强制执行文件系统和网络隔离。

为什么沙箱很重要
--------

传统的基于权限的安全性需要对 bash 命令进行持续的用户批准。虽然这提供了控制，但可能导致：

*   **批准疲劳**：重复点击”批准”可能导致用户对他们批准的内容关注度降低
*   **生产力降低**：持续的中断会减慢开发工作流程
*   **自主性受限**：当等待批准时，Claude Code 无法高效工作

沙箱通过以下方式解决这些挑战：

1.  **定义清晰的边界**：精确指定 Claude Code 可以访问的目录和网络主机
2.  **减少权限提示**：沙箱内的安全命令不需要批准
3.  **维护安全性**：尝试访问沙箱外的资源会触发立即通知
4.  **启用自主性**：Claude Code 可以在定义的限制内更独立地运行

工作原理
----

### 文件系统隔离

沙箱 bash 工具将文件系统访问限制在特定目录：

*   **默认写入行为**：对当前工作目录及其子目录的读写访问
*   **默认读取行为**：对整个计算机的读取访问，除了某些被拒绝的目录
*   **被阻止的访问**：无法在没有明确权限的情况下修改当前工作目录外的文件
*   **可配置**：通过设置定义自定义允许和拒绝的路径

您可以使用设置中的 `sandbox.filesystem.allowWrite` 向其他路径授予写入访问权限。这些限制在操作系统级别强制执行（macOS 上的 Seatbelt，Linux 上的 bubblewrap），因此它们适用于所有子进程命令，包括 `kubectl`、`terraform` 和 `npm` 等工具，而不仅仅是 Claude 的文件工具。

### 网络隔离

网络访问通过在沙箱外运行的代理服务器进行控制：

*   **域名限制**：只能访问批准的域名
*   **用户确认**：新的域名请求会触发权限提示（除非启用了 [`allowManagedDomainsOnly`](about:/docs/zh-CN/settings#sandbox-settings)，它会自动阻止非允许的域名）
*   **自定义代理支持**：高级用户可以在出站流量上实现自定义规则
*   **全面覆盖**：限制适用于所有脚本、程序和由命令生成的子进程

### 操作系统级强制执行

沙箱 bash 工具利用操作系统安全原语：

*   **macOS**：使用 Seatbelt 进行沙箱强制执行
*   **Linux**：使用 [bubblewrap](https://github.com/containers/bubblewrap) 进行隔离
*   **WSL2**：使用 bubblewrap，与 Linux 相同

不支持 WSL1，因为 bubblewrap 需要仅在 WSL2 中可用的内核功能。 这些操作系统级限制确保由 Claude Code 命令生成的所有子进程都继承相同的安全边界。

入门
--

### 前置条件

在 **macOS** 上，沙箱使用内置的 Seatbelt 框架开箱即用。 在 **Linux 和 WSL2** 上，首先安装所需的包：

*   Ubuntu/Debian
    
*   Fedora
    

```
sudo apt-get install bubblewrap socat

```


```
sudo dnf install bubblewrap socat

```


### 启用沙箱

您可以通过运行 `/sandbox` 命令来启用沙箱：

这会打开一个菜单，您可以在其中选择沙箱模式。如果缺少所需的依赖项（例如 Linux 上的 `bubblewrap` 或 `socat`），菜单会显示您平台的安装说明。 默认情况下，如果沙箱无法启动（缺少依赖项、不支持的平台或平台限制），Claude Code 会显示警告并在没有沙箱的情况下运行命令。要使其成为硬失败，请将 [`sandbox.failIfUnavailable`](about:/docs/zh-CN/settings#sandbox-settings) 设置为 `true`。这适用于需要沙箱作为安全门的托管部署。

### 沙箱模式

Claude Code 提供两种沙箱模式： **自动允许模式**：Bash 命令将尝试在沙箱内运行，并自动允许而无需权限。无法沙箱化的命令（例如需要访问非允许主机的网络访问的命令）会回退到常规权限流程。您配置的显式询问/拒绝规则始终被尊重。 **常规权限模式**：所有 bash 命令都通过标准权限流程，即使是沙箱化的。这提供了更多控制，但需要更多批准。 在两种模式中，沙箱都强制执行相同的文件系统和网络限制。区别仅在于沙箱化命令是自动批准还是需要明确权限。

### 配置沙箱

通过 `settings.json` 文件自定义沙箱行为。有关完整的配置参考，请参阅 [Settings](about:/docs/zh-CN/settings#sandbox-settings)。

#### 向特定路径授予子进程写入访问权限

默认情况下，沙箱化命令只能写入当前工作目录。如果子进程命令（如 `kubectl`、`terraform` 或 `npm`）需要在项目目录外写入，请使用 `sandbox.filesystem.allowWrite` 向特定路径授予访问权限：

```
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "allowWrite": ["~/.kube", "/tmp/build"]
    }
  }
}

```


这些路径在操作系统级别强制执行，因此在沙箱内运行的所有命令（包括其子进程）都尊重它们。当工具需要对特定位置的写入访问时，这是推荐的方法，而不是使用 `excludedCommands` 将工具从沙箱中排除。 当在多个 [settings scopes](about:/docs/zh-CN/settings#settings-precedence) 中定�� `allowWrite`（或 `denyWrite`/`denyRead`/`allowRead`）时，数组被**合并**，这意味着来自每个范围的路径被组合，而不是替换。例如，如果托管设置允许写入 `/opt/company-tools`，用户在其个人设置中添加 `~/.kube`，则两个路径都包含在最终沙箱配置中。这意味着用户和项目可以扩展列表而无需复制或覆盖由更高优先级范围设置的路径。 路径前缀控制路径的解析方式：


|前缀     |含义                               |示例                                       |
|-------|---------------------------------|-----------------------------------------|
|/      |从文件系统根目录的绝对路径                    |/tmp/build 保持 /tmp/build                 |
|~/     |相对于主目录                           |~/.kube 变为 $HOME/.kube                   |
|./ 或无前缀|相对于项目设置的项目根目录，或相对于用户设置的 ~/.claude|项目设置中的 ./output 解析为 <project-root>/output|


较旧的 `//path` 前缀用于绝对路径仍然有效。如果您之前使用单斜杠 `/path` 期望项目相对解析，请切换到 `./path`。此语法与 [Read and Edit](about:/docs/zh-CN/permissions#read-and-edit) 权限规则不同，后者使用 `//path` 表示绝对路径，`/path` 表示项目相对路径。沙箱文件系统路径使用标准约定：`/tmp/build` 是绝对路径。 您也可以使用 `sandbox.filesystem.denyWrite` 和 `sandbox.filesystem.denyRead` 拒绝写入或读取访问。这些与来自 `Edit(...)` 和 `Read(...)` 权限规则的任何路径合并。要重新允许读取被拒绝区域内的特定路径，请使用 `sandbox.filesystem.allowRead`，它优先于 `denyRead`。当在托管设置中启用 `allowManagedReadPathsOnly` 时，仅尊重托管 `allowRead` 条目；用户、项目和本地 `allowRead` 条目被忽略。`denyRead` 仍然从所有来源合并。 例如，要阻止从整个主目录读取，同时仍允许从当前项目读取，请将此添加到您的项目的 `.claude/settings.json`：

```
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "denyRead": ["~/"],
      "allowRead": ["."]
    }
  }
}

```


`allowRead` 中的 `.` 解析为项目根目录，因为此配置位于项目设置中。如果您将相同的配置放在 `~/.claude/settings.json` 中，`.` 将解析为 `~/.claude`，项目文件将保持被 `denyRead` 规则阻止。

安全优势
----

### 防止提示注入

即使攻击者通过提示注入成功操纵 Claude Code 的行为，沙箱也确保您的系统保持安全： **文件系统保护：**

*   无法修改关键配置文件，如 `~/.bashrc`
*   无法修改 `/bin/` 中的系统级文件
*   无法读取在您的 [Claude 权限设置](about:/docs/zh-CN/permissions#manage-permissions) 中被拒绝的文件

**网络保护：**

*   无法向攻击者控制的服务器泄露数据
*   无法从未授权的域下载恶意脚本
*   无法向未批准的服务进行意外的 API 调用
*   无法联系任何未明确允许的域

**监控和控制：**

*   所有在沙箱外的访问尝试都在操作系统级别被阻止
*   当边界被测试时，您会收到立即通知
*   您可以选择拒绝、允许一次或永久更新您的配置

### 减少攻击面

沙箱限制了以下可能造成的损害：

*   **恶意依赖项**：具有有害代码的 NPM 包或其他依赖项
*   **被破坏的脚本**：具有安全漏洞的构建脚本或工具
*   **社会工程**：欺骗用户运行危险命令的攻击
*   **提示注入**：欺骗 Claude 运行危险命令的攻击

### 透明操作

当 Claude Code 尝试访问沙箱外的网络资源时：

1.  操作在操作系统级别被阻止
2.  您会收到立即通知
3.  您可以选择：
    *   拒绝请求
    *   允许一次
    *   更新您的沙箱配置以永久允许它

安全限制
----

*   网络沙箱限制：网络过滤系统通过限制进程允许连接的域来运行。它不会以其他方式检查通过代理的流量，用户负责确保他们只在其策略中允许受信任的域。

*   通过 Unix Sockets 的权限提升：`allowUnixSockets` 配置可能会无意中授予对可能导致沙箱绕过的强大系统服务的访问权限。例如，如果它用于允许访问 `/var/run/docker.sock`，这将有效地通过利用 docker socket 授予对主机系统的访问权限。鼓励用户仔细考虑他们通过沙箱允许的任何 unix sockets。
*   文件系统权限提升：过于宽泛的文件系统写入权限可能导致权限提升攻击。允许写入包含 `$PATH` 中的可执行文件、系统配置目录或用户 shell 配置文件（`.bashrc`、`.zshrc`）的目录可能导致当其他用户或系统进程访问这些文件时在不同的安全上下文中执行代码。
*   Linux 沙箱强度：Linux 实现提供强大的文件系统和网络隔离，但包括一个 `enableWeakerNestedSandbox` 模式，使其能够在 Docker 环境中工作而无需特权命名空间。此选项大大削弱了安全性，应仅在其他隔离被强制执行的情况下使用。

沙箱如何��权限相关
----------

沙箱和 [permissions](https://code.claude.com/docs/zh-CN/permissions) 是互补的安全层，协同工作：

*   **权限**控制 Claude Code 可以使用哪些工具，在任何工具运行之前进行评估。它们适用于所有工具：Bash、Read、Edit、WebFetch、MCP 和其他工具。
*   **沙箱**提供操作系统级强制执行，限制 Bash 命令在文件系统和网络级别可以访问的内容。它仅适用于 Bash 命令及其子进程。

文件系统和网络限制通过沙箱设置和权限规则进行配置：

*   使用 `sandbox.filesystem.allowWrite` 向工作目录外的路径授予子进程写入访问权限
*   使用 `sandbox.filesystem.denyWrite` 和 `sandbox.filesystem.denyRead` 阻止子进程访问特定路径
*   使用 `sandbox.filesystem.allowRead` 重新允许读取被拒绝区域内的特定路径
*   使用 `Read` 和 `Edit` 拒绝规则阻止访问特定文件或目录
*   使用 `WebFetch` 允许/拒绝规则控制域名访问
*   使用沙箱 `allowedDomains` 控制 Bash 命令可以到达的域名

来自 `sandbox.filesystem` 设置和权限规则的路径被合并到最终沙箱配置中。 此 [repository](https://github.com/anthropics/claude-code/tree/main/examples/settings) 包括常见部署场景的启动设置配置，包括沙箱特定的示例。使用这些作为起点，并根据您的需求调整它们。

高级用法
----

### 自定义代理配置

对于需要高级网络安全的组织，您可以实现自定义代理以：

*   解密和检查 HTTPS 流量
*   应用自定义过滤规则
*   记录所有网络请求
*   与现有安全基础设施集成

```
{
  "sandbox": {
    "network": {
      "httpProxyPort": 8080,
      "socksProxyPort": 8081
    }
  }
}

```


### 与现有安全工具的集成

沙箱 bash 工具与以下工具配合使用：

*   **权限规则**：与 [permission settings](https://code.claude.com/docs/zh-CN/permissions) 结合以实现深度防御
*   **开发容器**：与 [devcontainers](https://code.claude.com/docs/zh-CN/devcontainer) 一起使用以获得额外隔离
*   **企业策略**：通过 [managed settings](about:/docs/zh-CN/settings#settings-precedence) 强制执行沙箱配置

最佳实践
----

1.  **从限制性开始**：从最小权限开始，根据需要扩展
2.  **监控日志**：查看沙箱违规尝试以了解 Claude Code 的需求
3.  **使用环境特定的配置**：开发与生产环境的不同沙箱规则
4.  **与权限结合**：将沙箱与 IAM 策略一起使用以实现全面安全
5.  **测试配置**：验证您的沙箱设置不会阻止合法工作流程

开源
--

沙箱运行时作为开源 npm 包提供，供您在自己的代理项目中使用。这使更广泛的 AI 代理社区能够构建更安全、更安全的自主系统。这也可以用于沙箱化您可能希望运行的其他程序。例如，要沙箱化 MCP 服务器，您可以运行：

```
npx @anthropic-ai/sandbox-runtime <command-to-sandbox>

```


有关实现细节和源代码，请访问 [GitHub repository](https://github.com/anthropic-experimental/sandbox-runtime)。

限制
--

*   **性能开销**：最小，但某些文件系统操作可能稍慢
*   **兼容性**：某些需要特定系统访问模式的工具可能需要配置调整，或者甚至可能需要在沙箱外运行
*   **平台支持**：支持 macOS、Linux 和 WSL2。不支持 WSL1。计划支持原生 Windows。

沙箱不涵盖的内容
--------

沙箱隔离 Bash 子进程。其他工具在不同的边界下运行：

*   **内置文件工具**：Read、Edit 和 Write 直接使用权限系统，而不是通过沙箱运行。请参阅 [permissions](https://code.claude.com/docs/zh-CN/permissions)。
*   **计算机使用**：当 Claude 在 macOS 上打开应用程序并控制您的屏幕时，它在您的实际桌面上运行，而不是在隔离的环境中。每个应用程序的权限提示控制每个应用程序。请参阅 [CLI 中的计算机使用](https://code.claude.com/docs/zh-CN/computer-use) 或 [Desktop 中的计算机使用](about:/docs/zh-CN/desktop#let-claude-use-your-computer)。

另请参阅
----

*   [Security](https://code.claude.com/docs/zh-CN/security) - 全面的安全功能和最佳实践
*   [Permissions](https://code.claude.com/docs/zh-CN/permissions) - 权限配置和访问控制
*   [Settings](https://code.claude.com/docs/zh-CN/settings) - 完整的配置参考
*   [CLI reference](https://code.claude.com/docs/zh-CN/cli-reference) - 命令行选项