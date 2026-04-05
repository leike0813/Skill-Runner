## 1. Vendor Resource Setup

- [x] 1.1 Download KaTeX CSS and JS to server/assets/static/vendor/katex/
- [x] 1.2 Download KaTeX font files (woff2, woff, ttf) to server/assets/static/vendor/katex/fonts/
- [x] 1.3 Download markdown-it to server/assets/static/vendor/markdown-it/
- [x] 1.4 Download markdown-it-texmath to server/assets/static/vendor/markdown-it-texmath/

## 2. Markdown Rendering Implementation

- [x] 2.1 Add vendor script references in run_observe.html
- [x] 2.2 Create renderMarkdown(text) helper function with XSS protection
- [x] 2.3 Configure markdown-it with html: false, breaks: true
- [x] 2.4 Configure texmath plugin with KaTeX engine for LaTeX support
- [x] 2.5 Integrate Markdown rendering in bubble mode chat messages
- [x] 2.6 Integrate Markdown rendering in plain mode chat messages
- [x] 2.7 Add Markdown rendering for thinking card content
- [x] 2.8 Add Markdown rendering for final summary content

## 3. CSS Styling

- [x] 3.1 Add code block styles (pre, code elements)
- [x] 3.2 Add table styles (table, th, td with borders and斑马纹)
- [x] 3.3 Add list styles (ul, ol, li)
- [x] 3.4 Add blockquote styles with left border
- [x] 3.5 Add heading styles (h1-h6)
- [x] 3.6 Add link styles with hover underline
- [x] 3.7 Add LaTeX formula rendering styles via KaTeX
- [x] 3.8 Adjust chat bubble line-height to 1.4
- [x] 3.9 Adjust plain mode line-height to 1.5
- [x] 3.10 Remove trailing margin from last child elements

## 4. Testing and Verification

- [x] 4.1 Test basic Markdown syntax (headings, lists, bold, italic)
- [x] 4.2 Test table rendering with multiple columns
- [x] 4.3 Test code block rendering (inline and fenced)
- [x] 4.4 Test LaTeX inline formula rendering ($E = mc^2$)
- [x] 4.5 Test LaTeX display formula rendering ($$...$$)
- [x] 4.6 Verify Plain/Bubble view switching preserves Markdown formatting
- [x] 4.7 Verify XSS protection (HTML tags are escaped)
- [x] 4.8 Test long message rendering performance

## 5. Documentation

- [x] 5.1 Create specs/markdown-render/spec.md with WHEN/THEN scenarios
- [x] 5.2 Update design.md with vendor resource management section
- [x] 5.3 Update .openspec.yaml status to completed
