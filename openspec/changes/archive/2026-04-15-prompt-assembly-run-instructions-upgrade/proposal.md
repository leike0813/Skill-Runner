## Why

The current prompt organization still couples two different concerns:

- engine-agnostic global execution constraints
- per-attempt skill invocation prompt assembly

Global constraints are injected as a hidden first-attempt prefix, while the actual skill invocation text is duplicated across `runner.json` prompts, shared templates, and adapter fallback strings. That makes prompt auditing less clear, keeps first-attempt special cases alive in runtime code, and makes engine prompt behavior harder to reason about.

## What Changes

- Replace the old first-attempt global prompt prefix with run-root instruction files:
  - `CLAUDE.md`
  - `GEMINI.md`
  - `AGENTS.md`
- Make adapter profiles declare the canonical skill invoke line template for each engine.
- Split prompt assembly into two explicit pieces:
  - invoke line
  - body prompt
- Keep `runner.json.entrypoint.prompts` as the body-prompt source only.
- Add a dedicated SSOT document describing prompt truth sources, composition order, engine translation, and runtime layout.

## Impact

- Affected code:
  - `prompt_builder_common`
  - `base_execution_adapter`
  - `run_skill_materialization_service`
  - adapter profile schema / loader / per-engine profiles
- Affected docs:
  - new `docs/prompt_organization_ssot.md`
  - aligned developer docs for adapter profile and onboarding
- Affected tests:
  - adapter profile loader
  - prompt builder common
  - run folder bootstrapper
  - gemini / claude prompt-related adapter tests
