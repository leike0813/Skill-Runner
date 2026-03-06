## 0. Rebuild Baseline

- [x] 0.1 Apply visual constraints from `artifacts/ui_style_rebuild_prompt.md` before template restyling.
- [x] 0.2 Keep route/API/protocol behavior unchanged while applying UI style updates.

## 1. Design System Foundation

- [x] 1.1 Create `static/css/design-system.css` with CSS custom properties (color palette, typography scale, spacing scale, border-radius, box-shadow, transition tokens)
- [x] 1.2 Add Inter font import via Google Fonts with system font stack fallback
- [x] 1.3 Define base reset and global styles (body, headings, links, code blocks)
- [x] 1.4 Define utility classes: `.card`, `.badge`, `.badge--success/warning/error/info`, `.btn`, `.btn--primary/secondary/danger`, `.table`, `.table--striped`
- [x] 1.5 Define layout utilities: `.container`, `.sidebar`, `.content-area`, `.page-header`, `.nav`
- [x] 1.6 Define micro-animation classes: hover transitions for buttons, table rows, cards, and expandable sections
- [x] 1.7 Configure static file serving for the CSS file in both Admin UI and E2E Client FastAPI apps

## 2. Admin Management UI — Base & Navigation

- [x] 2.1 Create or update Admin UI base template to import the shared CSS file and establish sidebar + content layout
- [x] 2.2 Restyle the home/navigation page (`ui/index.html`) with nav links styled as cards or sidebar items
- [x] 2.3 Restyle the settings page (`ui/settings.html`) with consistent form and panel styling

## 3. Admin Management UI — Skill Pages

- [x] 3.1 Restyle the skills table partial (`ui/partials/skills_table.html`) with design-system table and badge classes
- [x] 3.2 Restyle the skill detail page (`ui/skill_detail.html`) with cards for metadata, schema preview, and file browser
- [x] 3.3 Restyle the file preview partial (`ui/partials/file_preview.html`) with code-block styling

## 4. Admin Management UI — Engine Pages

- [x] 4.1 Restyle the engines page (`ui/engines.html`) and engines table partial (`ui/partials/engines_table.html`)
- [x] 4.2 Restyle the engine models page (`ui/engine_models.html`) and engine models panel partial
- [x] 4.3 Restyle the engine upgrade status partial (`ui/partials/engine_upgrade_status.html`)
- [x] 4.4 Restyle the install status partial (`ui/partials/install_status.html`)

## 5. Admin Management UI — Run Pages

- [x] 5.1 Restyle the runs page (`ui/runs.html`) and runs table partial (`ui/partials/runs_table.html`)
- [x] 5.2 Restyle the run detail page (`ui/run_detail.html`) with structured layout for state, logs, and events
- [x] 5.3 Restyle the run logs tail partial (`ui/partials/run_logs_tail.html`)

## 6. Admin Management UI — Settings Partials

- [x] 6.1 Restyle the settings logging panel partial (`ui/partials/settings_logging_panel.html`)
- [x] 6.2 Restyle the settings reset panel partial (`ui/partials/settings_reset_panel.html`)

## 7. E2E Example Client — Base & Core Pages

- [x] 7.1 Update E2E Client base template (`e2e_client/templates/base.html`) to import the shared CSS file and establish layout
- [x] 7.2 Restyle the home/skill list page (`e2e_client/templates/index.html`)
- [x] 7.3 Restyle the run form page (`e2e_client/templates/run_form.html`) with form controls, input groups, and engine/model selectors
- [x] 7.4 Restyle the run observation page (`e2e_client/templates/run_observe.html`) with panels for conversation, logs, and events

## 8. E2E Example Client — Run & Recording Pages

- [x] 8.1 Restyle the runs list page (`e2e_client/templates/runs.html`)
- [x] 8.2 Remove recordings list page residuals (`e2e_client/templates/recordings.html`) as replayless baseline.
- [x] 8.3 Remove recording detail page residuals (`e2e_client/templates/recording_detail.html`) as replayless baseline.
- [x] 8.4 Restyle the file preview partial (`e2e_client/templates/partials/file_preview.html`)

## 9. Auxiliary Pages

- [x] 9.1 Restyle the OAuth callback success page in `server/runtime/auth/callbacks.py` (`OAuthCallbackRouter.render()`) with inline styled HTML
- [x] 9.2 Restyle the OAuth callback error page in `server/runtime/auth/callbacks.py` (`OAuthCallbackRouter.render_error()`) with inline styled HTML
- [x] 9.3 Create a generic Jinja2 error page template for browser-facing error responses (404, 503, etc.)
- [x] 9.4 Add content negotiation in E2E Client and Admin UI error handlers to serve HTML error page for browser clients and JSON for API clients

## 10. Internationalization (i18n)

- [x] 10.1 Create JSON locale files (`locales/en.json`, `locales/zh.json`, `locales/fr.json`, `locales/ja.json`) with all UI string keys
- [x] 10.2 Implement locale resolution middleware: `?lang=` query → `lang` cookie → `Accept-Language` header → fallback `en`
- [x] 10.3 Register Jinja2 global function `t(key)` for both Admin UI and E2E Client template environments
- [x] 10.4 Implement language switcher component in Admin UI and E2E Client base templates
- [x] 10.5 Replace all hardcoded UI strings in Admin UI templates (17 files) with `{{ t('...') }}` calls
- [x] 10.6 Replace all hardcoded UI strings in E2E Client templates (8 files) with `{{ t('...') }}` calls
- [x] 10.7 Add client-side language detection to OAuth callback and error page inline HTML
