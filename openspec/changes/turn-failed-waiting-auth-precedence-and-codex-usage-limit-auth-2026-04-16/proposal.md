# turn-failed-waiting-auth-precedence-and-codex-usage-limit-auth-2026-04-16

Recent runtime governance work added `agent.turn_failed`, but the auth-remediation path still needs one more normalization pass:

- `turn.failed` is now visible as semantic runtime evidence
- `waiting_auth` already remains the canonical state when high-confidence auth remediation succeeds
- however, the precedence between those two concepts is not yet explicitly governed
- Codex usage-limit failures are still not classified as high-confidence auth/entitlement blockers
- when a run enters `waiting_auth`, the user can still lose the most useful semantic failure message that explains why authentication is needed

This change fixes that gap without altering the core chain:

- `turn_failed` remains engine evidence, not terminal state by itself
- `waiting_auth` continues to win canonical state when high-confidence auth evidence produces pending auth
- Codex usage-limit patterns become high-confidence auth detection so the run can enter `waiting_auth`
- semantic failure messages are preserved into the waiting-auth card via `pending_auth.last_error` / `instructions`

## Why

The existing chain already behaves like this in substance:

1. High-confidence auth evidence -> `waiting_auth`
2. Low-confidence or missing auth evidence -> `failed`

Adding `turn_failed` did not change that logic; it only made the engine failure evidence explicit. The remaining work is to govern the relationship cleanly and surface the reason to the user.
