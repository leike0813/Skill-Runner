## Why

The e2e waiting-user frontend currently treats non-`open_text` prompts as option-only interactions.

That hides the freeform reply composer whenever `ui_hints.options` are present, which prevents users from sending a custom instruction alongside the suggested actions.

## What Changes

- Keep prompt-card choices exactly as they are today.
- Keep the reply composer visible and enabled for non-`open_text` waiting-user prompts.
- Add a compact single-line reply-composer mode plus a dedicated localized placeholder for that case.
- Update the frontend upgrade guide to document the new waiting-user reply behavior.

## Impact

- No backend protocol changes.
- No management UI changes.
- E2E waiting-user prompts become “choice chips + freeform reply” instead of “choice chips only”.
