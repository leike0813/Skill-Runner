# Proposal: E2E Frontend Markdown Rendering

## Why

当前 e2e 前端聊天区使用纯文本渲染 (`white-space: pre-wrap`)，无法正确显示 Agent 返回的结构化内容：

1. **代码块** - 无语法高亮，难以阅读
2. **表格** - 无法显示结构化数据
3. **列表/标题** - 没有层次结构
4. **粗体/斜体** - 无法强调重点
5. **LaTeX 公式** - 无法渲染数学符号

用户需要一个轻量级的 Markdown 渲染方案来提升聊天内容的可读性。

## What

为 e2e 前端聊天区添加实时 Markdown 渲染能力，支持基础 Markdown 语法和 LaTeX 数学公式。

### Capabilities

1. **markdown-render** - Chat messages render Markdown syntax with proper styling
2. **latex-formula-render** - LaTeX math formulas render using KaTeX engine

### Constraints

- **轻量级** - 不引入复杂依赖，保持页面加载性能
- **向后兼容** - 不影响现有 Plain/Bubble 视图切换功能
- **安全** - 使用 markdown-it 内置的 HTML 转义进行 XSS 防护
- **本地部署** - 第三方库作为静态资源本地存放，不依赖外部 CDN

## How

### Technical Stack

- **Markdown Parser**: `markdown-it` v14 - 高性能、模块化
- **LaTeX Engine**: KaTeX v0.16.9 - 快速数学排版库
- **Math Plugin**: `markdown-it-texmath` v1.0.1 - Markdown 与 KaTeX 集成
- **加载方式**: 本地静态资源 (`/static/vendor/`)
- **渲染策略**: 纯前端渲染，无后端依赖

### Implementation Steps

1. **Vendor 资源准备**
   - 下载 KaTeX CSS、JS 和字体文件
   - 下载 markdown-it 主文件
   - 下载 markdown-it-texmath 插件
   - 存放于 `server/assets/static/vendor/` 目录

2. **前端集成**
   - 在 `run_observe.html` 中引用 vendor 资源
   - 创建 `renderMarkdown(text)` 辅助函数
   - 配置 markdown-it 和 texmath 插件
   - 替换聊天区的纯文本渲染逻辑

3. **样式设计**
   - 代码块样式（背景、边框、等宽字体）
   - 表格样式（边框、对齐、斑马纹）
   - 列表/引用/标题/链接样式
   - 行距优化（bubble: 1.4, plain: 1.5）

4. **XSS 防护**
   - 配置 `html: false` 禁用原始 HTML 标签
   - markdown-it 自动转义恶意脚本

### File Changes

**Modified:**
1. `e2e_client/templates/run_observe.html` - 添加 vendor 引用、渲染逻辑、样式

**Added (Vendor Resources):**
1. `server/assets/static/vendor/katex/` - KaTeX 库
2. `server/assets/static/vendor/markdown-it/` - markdown-it 库
3. `server/assets/static/vendor/markdown-it-texmath/` - LaTeX 插件

## Success Criteria

1. 聊天消息中的 Markdown 语法正确渲染（标题、列表、粗体、斜体、链接、引用）
2. 表格显示美观、可读，边框清晰
3. 代码块使用等宽字体，有背景区分
4. LaTeX 公式正确渲染（行内 `$...$` 和块级 `$$...$$`）
5. Plain/Bubble 视图切换功能正常，Markdown 格式保持
6. 页面加载性能无明显下降
7. XSS 防护生效，HTML 标签被转义
8. 聊天区行距适中，无多余空白
