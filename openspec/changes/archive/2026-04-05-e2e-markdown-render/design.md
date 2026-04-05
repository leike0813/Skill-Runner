# E2E Markdown Rendering Design

## Design Overview

本设计通过引入 `markdown-it` 库实现 e2e 前端聊天区的 Markdown 实时渲染，重点支持基础语法和表格。

## Technical Stack

### Markdown Parser: markdown-it

选择理由：
- **高性能** - 解析速度业界领先
- **模块化** - 可按需引入扩展
- **稳定** - 广泛使用的成熟库
- **本地部署** - 无需外部 CDN 依赖

### 本地静态资源

```html
<script src="/static/vendor/markdown-it/markdown-it.min.js"></script>
```

文件位置：`server/assets/static/vendor/markdown-it/markdown-it.min.js`

### 配置

```javascript
const md = window.markdownit({
    html: false,        // 禁用 HTML 标签（XSS 防护）
    xhtmlOut: false,
    breaks: true,       // 支持段落内换行
    langPrefix: 'language-',
    linkify: false,     // 不自动转换 URL 为链接
    typographer: false,
    quotes: '""\'\'',
    highlight: null     // 暂不实现语法高亮
});
```

## Implementation Details

### 渲染逻辑集成

当前聊天区渲染逻辑位于 `run_observe.html` 的内联 script 中。修改方案：

```javascript
// 原始代码（纯文本）
bubble.textContent = message.text;

// 修改后（Markdown 渲染）
bubble.innerHTML = md.render(message.text);
```

### 样式设计

```css
/* 代码块样式 */
.chat-bubble pre {
    background: #f6f8fa;
    padding: 12px;
    border-radius: 6px;
    overflow: auto;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
}

.chat-bubble code {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
    background: #f6f8fa;
    padding: 2px 6px;
    border-radius: 4px;
}

.chat-bubble pre code {
    background: transparent;
    padding: 0;
}

/* 表格样式 */
.chat-bubble table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 14px;
}

.chat-bubble th,
.chat-bubble td {
    border: 1px solid #d0d7de;
    padding: 8px 12px;
    text-align: left;
}

.chat-bubble th {
    background: #f6f8fa;
    font-weight: 600;
}

.chat-bubble tr:nth-child(even) {
    background: #f6f8fa;
}

/* 列表样式 */
.chat-bubble ul,
.chat-bubble ol {
    padding-left: 24px;
    margin: 8px 0;
}

.chat-bubble li {
    margin: 4px 0;
}

/* 引用样式 */
.chat-bubble blockquote {
    border-left: 4px solid #d0d7de;
    padding-left: 16px;
    margin: 12px 0;
    color: #656d76;
}

/* 标题样式 */
.chat-bubble h1,
.chat-bubble h2,
.chat-bubble h3,
.chat-bubble h4,
.chat-bubble h5,
.chat-bubble h6 {
    margin: 16px 0 8px;
    font-weight: 600;
}

/* 链接样式 */
.chat-bubble a {
    color: #0969da;
    text-decoration: none;
}

.chat-bubble a:hover {
    text-decoration: underline;
}
```

## LaTeX Formula Rendering

### KaTeX Engine

使用 KaTeX 作为 LaTeX 公式渲染引擎：

```html
<!-- KaTeX CSS -->
<link rel="stylesheet" href="/static/vendor/katex/katex.min.css">
<!-- KaTeX JS -->
<script src="/static/vendor/katex/katex.min.js"></script>
```

### markdown-it-texmath Plugin

使用 `markdown-it-texmath` 插件集成 KaTeX 到 markdown-it：

```html
<script src="/static/vendor/markdown-it-texmath/texmath.min.js"></script>
```

配置：
```javascript
md.use(window.texmath, {
    engine: window.katex,
    delimiters: 'dollars',  // 支持 $inline$ 和 $$display$$
    katexOptions: {
        throwOnError: false,
        output: 'htmlAndMath',
        displayMode: false
    }
});
```

### 支持的 LaTeX 语法

- **行内公式**: `$E = mc^2$`
- **块级公式**: `$$\sum_{i=1}^n x_i$$`
- **分数**: `$\frac{a}{b}$`
- **上下标**: `$x^2$, $x_i$`
- **根号**: `$\sqrt{x}$`
- **希腊字母**: `$\alpha$, $\beta$, $\gamma$`
- **积分**: `$\int_a^b f(x)dx$`
- **求和**: `$\sum_{i=1}^n x_i$`

### Plain Mode 适配

Plain mode 使用 `.chat-plain-body` 类，同样需要应用 Markdown 渲染：

```javascript
// Plain mode 渲染
plainBody.innerHTML = md.render(message.text);
```

## Security Considerations

### XSS 防护

`markdown-it` 默认会转义 HTML 标签。配置时设置 `html: false` 可防止用户注入恶意脚本：

```javascript
const md = window.markdownit({
    html: false,  // 关键：禁用原始 HTML
    // ...
});
```

### 额外防护（可选）

如果需要更严格的防护，可以在渲染前进行额外的 sanitize：

```javascript
function sanitizeMarkdown(text) {
    // 移除潜在的危险标签
    return text.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
}
```

## Performance Considerations

1. **本地部署** - 无需外部 CDN 请求，加载更可靠
2. **按需渲染** - 仅在消息到达时渲染，非批量预渲染
3. **最小化版本** - 使用 `.min.js` 减少下载体积

### Bundle Size

- markdown-it minified: ~121KB
- KaTeX (CSS + JS): ~294KB
- KaTeX fonts (15 files): ~320KB
- markdown-it-texmath: ~6KB
- **总计**: ~741KB (首次加载，后续可缓存)

## Vendor 资源管理

### 资源位置

所有第三方库存放在 `server/assets/static/vendor/` 目录下：

```
server/assets/static/vendor/
├── katex/
│   ├── katex.min.css              # KaTeX 样式
│   ├── katex.min.js               # KaTeX 渲染引擎
│   └── fonts/                     # KaTeX 字体文件
│       ├── KaTeX_Main-Regular.woff2
│       ├── KaTeX_Main-Italic.woff2
│       ├── KaTeX_Math-Italic.woff2
│       ├── KaTeX_Size1-Regular.woff2
│       ├── KaTeX_Size2-Regular.woff2
│       ├── KaTeX_Main-Regular.woff
│       ├── KaTeX_Main-Italic.woff
│       ├── KaTeX_Math-Italic.woff
│       ├── KaTeX_Size1-Regular.woff
│       ├── KaTeX_Size2-Regular.woff
│       ├── KaTeX_Main-Regular.ttf
│       ├── KaTeX_Main-Italic.ttf
│       ├── KaTeX_Math-Italic.ttf
│       ├── KaTeX_Size1-Regular.ttf
│       └── KaTeX_Size2-Regular.ttf
├── markdown-it/
│   └── markdown-it.min.js         # Markdown 解析器
└── markdown-it-texmath/
    └── texmath.min.js             # LaTeX 公式渲染插件
```

### 更新策略

当需要更新库版本时：
1. 从 jsDelivr 下载新版本到对应目录
2. 更新 `run_observe.html` 中的引用（如果需要）
3. 更新本文档中的版本说明

## Fallback Strategy

如果本地资源加载失败（文件不存在）：
```javascript
if (!window.markdownit) {
    console.warn('Markdown parser not loaded, falling back to plain text');
    // 降级为纯文本渲染
}
```
