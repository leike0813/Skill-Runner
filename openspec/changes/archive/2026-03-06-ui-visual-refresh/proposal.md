## Why

The Skill Runner v0.4.0 release brings a public-ready backend, but both the **Admin Management UI** and the **E2E Example Client** still use bare-minimum inline styling with no design system. The current look is purely functional — unstyled HTML tables, no spacing consistency, default browser typography, and raw JSON error responses. For a public-facing project, the UI needs a visual refresh that conveys professionalism without altering any runtime logic.

## Style Input Source

This change MUST follow the style constraints documented in:

- `artifacts/ui_style_rebuild_prompt.md`

The file above is the canonical style guidance for this reimplementation pass. It constrains visual direction only and does not permit route/protocol behavior changes.

## What Changes

- Introduce a **shared CSS design system** (color palette, typography, spacing, layout utilities) used by both UIs.
- Restyle all **Admin Management UI** pages: home/navigation, skill browser, skill detail, engine management, engine models, runs list, run detail, settings, and all HTMX partials.
- Restyle all **E2E Example Client** pages: home/skill list, run form, run observation, runs list, recordings, recording detail, and file preview.
- Beautify **auxiliary pages**:
  - OAuth callback success/error page — currently returns raw inline HTML from `OAuthCallbackRouter.render()`.
  - Error/exception responses (e.g., backend unreachable) — present a minimal, styled error page instead of raw JSON.
- Add **micro-animations** for interactive elements (hover states, transitions, loading indicators).
- Ensure **responsive layout** basics (comfortable on desktop; not broken on tablet-width).
- Add **multi-language (i18n) support** for both UIs with an in-page language switcher. Initial languages: Chinese (zh), English (en), French (fr), Japanese (ja).

## Capabilities

### New Capabilities
- `ui-design-system`: Shared CSS design tokens (colors, typography, spacing, shadows, animations) and reusable utility classes for both Admin UI and E2E Client.
- `ui-auxiliary-pages`: Styled OAuth callback success/error page and generic error page template for non-JSON error responses.
- `ui-i18n`: Multi-language support with JSON-based translation files for zh/en/fr/ja, Jinja2 translation integration, in-page language switcher, and locale persistence via cookie/query parameter.

### Modified Capabilities
_(No spec-level requirement changes — this is a visual-only refresh. Existing UI specs define page structure and interactions which remain unchanged.)_

## Impact

- **Admin UI templates**: All 17 files in `server/assets/templates/ui/` (7 pages + 10 partials).
- **E2E Client templates**: All 8 files in `e2e_client/templates/` (6 pages + 1 partial + base layout).
- **OAuth callback renderer**: `server/runtime/auth/callbacks.py` (`OAuthCallbackRouter.render()` / `render_error()`).
- **Error handlers**: Any route returning raw exception detail to the browser.
- **Static assets**: New CSS file(s) to be served; possible addition of a web font import.
- **Translation files**: New JSON locale files for zh/en/fr/ja.
- **Template engine integration**: Jinja2 globals/filters for translation lookup.
- **No runtime/API logic changes**: All routing, job orchestration, and runtime behavior remain untouched. i18n is a presentation-layer concern only.
