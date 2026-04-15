## Context

The backend already owns canonical structured-output interpretation:

- pending branch: `__SKILL_DONE__ = false` + `message` + `ui_hints`
- final branch: `__SKILL_DONE__ = true` + business payload
- fallback paths: raw text or legacy/default waiting behavior

What remained inconsistent was frontend display:

- chat bubbles were still effectively coupled to raw text
- pending cards still reused prompt/message fields instead of reading `ui_hints` as the real prompt-card surface
- the E2E client kept a separate final-summary card even after chat became the canonical display surface

## Goals / Non-Goals

**Goals**
- Make structured-output display backend-driven.
- Keep `/chat` as the single conversation surface for frontend chat panels.
- Split responsibilities cleanly:
  - chat = information
  - prompt card = interaction guidance
- Preserve existing HTTP paths and public event types.

**Non-Goals**
- Do not redesign `/chat` into a new API.
- Do not change `PendingInteraction` external shape.
- Do not add a second public event type for structured-output display.
- Do not move management UI into a full interaction client.

## Decisions

### 1. Add display fields to `assistant.message.final`

`assistant.message.final.data.text` remains for compatibility, but frontend-facing display semantics are projected into:

- `display_text`
- `display_format`
- `display_origin`
- optional `structured_payload`

This keeps protocol compatibility while giving chat replay one canonical display input.

### 2. Project pending/final display before chat replay

The backend formatter interprets raw final text as follows:

- pending branch → chat text = `message`
- final branch → chat text = markdown nested list generated from the payload without `__SKILL_DONE__`
- fallback/unparseable output → chat text = raw normalized text

That projection happens before `/chat` derivation, so frontends do not dispatch on structured JSON.

### 3. Make prompt cards consume `ui_hints` only

The pending prompt card keeps using `/interaction/pending`, but its display source changes:

- title/body = `ui_hints.prompt`
- hint = `ui_hints.hint`
- options/files = `ui_hints.options` / `ui_hints.files`
- not `message`

If `ui_hints.prompt` is missing, the card falls back to the stable default prompt instead of copying chat text.

### 4. Remove the final summary card

The final summary card is now redundant because final structured output is already rendered in chat. Keeping it would violate the rule that information belongs in chat and interaction affordances belong in cards.

## Risks / Trade-offs

- Backend projection adds another interpretation step for `assistant.message.final`. Mitigation: keep `text` untouched and make `display_*` additive.
- Management UI now renders markdown in chat. Mitigation: use a lightweight markdown renderer and keep the change limited to chat message bodies.
- Legacy waiting/fallback flows still exist. Mitigation: prompt cards degrade to default open-text behavior while chat continues showing the terminal/fallback output.

## Migration Plan

1. Add backend display projection for `assistant.message.final`.
2. Update chat replay derivation to prefer projected display text.
3. Update E2E and management templates to stop local structured-output dispatch.
4. Remove the E2E final summary card.
5. Publish frontend guidance and lock behavior with tests.
