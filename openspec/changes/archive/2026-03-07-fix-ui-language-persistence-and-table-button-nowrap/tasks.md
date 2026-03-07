## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks and delta specs for language persistence and table button nowrap.

## 2. Language Persistence

- [x] 2.1 Update server and E2E i18n middleware to persist `lang` cookie when `?lang=` is provided.
- [x] 2.2 Update language switcher templates to keep existing query params and only override `lang`.
- [x] 2.3 Verify cross-page navigation keeps selected language for both management UI and E2E client.

## 3. Table Button No-Wrap

- [x] 3.1 Update shared design-system CSS to prevent table action button text wrapping/collapsing.
- [x] 3.2 Add or align table action container classes in affected templates (management UI + E2E where needed).
- [x] 3.3 Verify narrow viewport rendering keeps button shape and readability.

## 4. Tests & Validation

- [x] 4.1 Update/add tests for language persistence behavior.
- [x] 4.2 Update/add tests for table button no-wrap semantics.
- [x] 4.3 Run targeted pytest suite and validate this OpenSpec change.
