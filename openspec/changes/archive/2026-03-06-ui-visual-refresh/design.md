## Context

Both the Admin Management UI (`server/assets/templates/ui/`, 17 Jinja2 templates) and the E2E Example Client (`e2e_client/templates/`, 8 Jinja2 templates) currently use inline styles with no shared design language. The OAuth callback handler (`server/runtime/auth/callbacks.py`) returns raw inline HTML. Error scenarios surface raw JSON or Python exception text to the browser. With v0.4.0, the project is public-facing and the UI must present a professional, cohesive appearance.

All styles are currently authored inline within individual HTML templates — there are no CSS files in the project. The Admin UI uses HTMX for dynamic partial swaps; the E2E Client uses vanilla JS + SSE. Both share a Jinja2 templating approach.

Style constraints for this redesign are defined in:

- `artifacts/ui_style_rebuild_prompt.md`

Implementation must treat this file as visual guidance SSOT for this change and keep behavior contracts unchanged.

## Goals / Non-Goals

**Goals:**
- Establish a shared CSS design system (tokens + utility classes) consumed by both UIs.
- Modernize all page and partial templates with consistent spacing, typography, color, and layout.
- Add tasteful micro-animations for hover, focus, transitions, and loading states.
- Beautify OAuth callback success/error pages and generic error page rendering.
- Keep the visual refresh scope to CSS and HTML templates only — no runtime logic changes.

**Non-Goals:**
- No migration to a CSS framework (Tailwind, Bootstrap). Vanilla CSS only.
- No SPA rewrite — both UIs remain server-rendered Jinja2 + HTMX/vanilla JS.
- No third-party i18n framework (Flask-Babel, etc.) — lightweight JSON + Jinja2 filter approach.
- No new pages, routes, or API endpoints.
- No changes to HTMX partial swap contracts (attribute names, target IDs remain stable).
- No mobile-first responsive overhaul (desktop-focused with reasonable tablet resilience).

## Decisions

### 1. Single shared CSS file served as static asset

**Decision**: Create one CSS file (`static/css/design-system.css`) imported by both Admin UI `base.html` and E2E Client `base.html`.

**Rationale**: Both UIs share the same brand; a single design-system file ensures consistency without duplication. Versus two separate files: simpler maintenance, one cache entry. Versus inline styles: enables theming, reduces template noise.

**Alternative considered**: CSS-in-template via Jinja2 blocks. Rejected — doesn't scale, impossible to share cross-app.

### 2. CSS custom properties for design tokens

**Decision**: Use CSS custom properties (`--color-*`, `--space-*`, `--font-*`, `--radius-*`, `--shadow-*`) on `:root`.

**Rationale**: Native, zero-build, easy to override for future dark-mode or theming. Versus Sass variables: adds build step; versus utility classes only: less semantic.

### 3. Color palette — dark-accented neutral scheme

**Decision**: Dark sidebar/nav + light content area. Accent color for primary actions. Neutral grays for tables and cards.

**Rationale**: Matches developer-tool aesthetics (GitHub, Vercel, Linear). Dark chrome conveys professionalism; light content preserves readability for data-heavy pages (skill detail, run logs, event tables).

### 4. Typography — system font stack + optional Inter import

**Decision**: `font-family: 'Inter', system-ui, -apple-system, sans-serif` with a Google Fonts `<link>` for Inter. Fallback to system fonts if offline.

**Rationale**: Inter is the de facto standard for developer tools. System stack fallback ensures zero-layout-shift if the font fails to load.

### 5. OAuth callback & error pages — self-contained styled HTML

**Decision**: Modify `OAuthCallbackRouter.render()` and `.render_error()` to return full styled HTML pages using inline `<style>` blocks referencing the same design tokens, rather than importing the CSS file.

**Rationale**: These pages are served outside the Jinja2 template hierarchy (they're assembled in Python code). Embedding a minimal self-contained style block keeps them decoupled from the template engine while still looking consistent.

### 6. Error responses — HTML error page for browser clients only

**Decision**: Add a Jinja2 error page template. Use content negotiation (`Accept: text/html`): if the client accepts HTML, render the styled error page; otherwise return JSON. This applies to the E2E Client proxy layer and the management UI error handler.

**Rationale**: API consumers must still get JSON. Browser clients (direct navigation) should see a styled page. The existing E2E Client `_sse_error_frame()` helper is SSE-only and remains unchanged.

### 7. JSON-based translation files per locale

**Decision**: Store translations as flat JSON files (`locales/{lang}.json`) with dot-path keys (e.g., `"nav.home"`, `"engine.status.online"`). Load all locale files at startup into a Python dict. Expose a Jinja2 global function `t(key)` that resolves the key against the current request locale.

**Rationale**: Simple, zero-dependency, fast lookup. The total UI string corpus is small (<500 keys) so in-memory is fine. Versus gettext/PO files: more complex toolchain; versus per-template strings: impossible to maintain across 4 languages.

**Alternative considered**: Flask-Babel / Babel. Rejected — adds dependency, PO compilation step, and is designed for larger-scale apps. Overkill for ~25 templates.

### 8. Locale resolution and persistence

**Decision**: Locale is resolved in order: (1) `?lang=xx` query parameter, (2) `lang` cookie, (3) `Accept-Language` header, (4) fallback to `en`. When the user selects a language from the switcher, set a `lang` cookie and reload.

**Rationale**: Cookie persistence means the choice "sticks" across navigation. Query param override enables bookmarkable locale links. Accept-Language provides a sensible default without user action.

### 9. Language switcher component

**Decision**: A compact dropdown/pill row in the page header showing `EN | 中文 | FR | 日本語`. Clicking sets `?lang=xx` which triggers a reload with cookie set server-side.

**Rationale**: Visible, simple, no JS framework needed. Consistent placement in both Admin UI and E2E Client headers.

### 10. Auxiliary pages use hardcoded multi-language strings

**Decision**: OAuth callback and error pages (which render outside Jinja2) embed a small inline JS snippet that selects the display string based on `navigator.language` or the `lang` cookie. No server-side locale resolution for these pages.

**Rationale**: These pages are self-contained HTML strings assembled in Python — they don't go through the Jinja2 template engine. A client-side approach keeps them decoupled while still multi-lingual.

## Risks / Trade-offs

- **Risk**: Inline-to-CSS migration may break existing HTMX partial swap styling if partials rely on parent inline styles.  
  → **Mitigation**: Move styles bottom-up (partials first, pages second). Test each partial in isolation via HTMX swap before proceeding.

- **Risk**: Google Fonts import adds an external dependency and may be unavailable in air-gapped deployments.  
  → **Mitigation**: System font stack fallback. The font is purely aesthetic — layout doesn't depend on Inter metrics.

- **Risk**: Translation key drift — templates reference keys that don't exist in all locale files.
  → **Mitigation**: Use English (`en.json`) as the canonical key source. Other locale files must have the same key set. A simple CI/dev script can diff keys across files.

- **Risk**: Template changes across 25+ files create a large diff that's hard to review.  
  → **Mitigation**: Structured task breakdown by page group. Each task is reviewable independently.
