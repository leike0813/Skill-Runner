## Context

The repository already has the canonical output-schema direction:

- phase 0A fixed the JSON-only final/pending contract
- phase 1 materialized canonical run-scoped schema artifacts under `.audit/contracts/`
- later phases introduced repair governance, pending-source cutover, and compatibility-path tightening

What changed in this implementation slice is not a small adapter flag tweak. Runtime now has a cross-cutting structured-output pipeline that affects:

- command construction
- adapter profiles
- run-scoped schema artifact selection
- skill patch prompt injection
- parsed payload normalization before orchestration consumes output

The key constraint is that canonical `target_output_schema.json` must remain the SSOT. Engine-specific transport constraints, especially Codex's JSON Schema subset, must be handled as derived compatibility assets rather than by mutating the canonical contract.

## Goals / Non-Goals

**Goals:**
- Define a single runtime pipeline for structured-output compatibility instead of keeping Codex/Claude handling scattered across engine-local helpers.
- Make adapter profiles the declarative source for structured-output behavior selection.
- Preserve canonical schema artifacts as the only machine-truth contract while allowing engine-compatible derived artifacts.
- Ensure prompt-contract selection and schema CLI injection are coordinated by one runtime decision path.
- Ensure engine-specific transport payloads are canonicalized back to the canonical final/pending shape before orchestration consumes them.

**Non-Goals:**
- Do not change the canonical output contract itself.
- Do not add new public HTTP, FCMP, or RASP protocol fields.
- Do not require every engine to implement a compatibility translator in this slice.
- Do not move waiting/completion policy or repair semantics into a new phase here.
- Do not make compat artifacts replace canonical `.audit/contracts/target_output_schema.json`.

## Decisions

### Decision 1: Structured output compatibility becomes a fixed runtime pipeline

Runtime uses a shared pipeline with three fixed responsibilities:

1. choose the effective machine schema artifact for engine dispatch
2. choose the effective prompt contract artifact for patch injection
3. canonicalize parsed structured payloads back to the canonical shape

Why:
- This removes repeated engine-branch logic from command builders and prompt injection sites.
- It gives future engines a standard insertion point without changing orchestration semantics.

Alternatives considered:
- Keep separate engine-local helpers for Codex and Claude.
  Rejected because the repo already hit drift between CLI schema injection and prompt summary generation.
- Put all translation logic directly into the orchestrator.
  Rejected because command builders and patchers need the same decision before orchestration sees the result.

### Decision 2: Adapter profile is the declarative strategy surface

`adapter_profile.json` declares:

- whether schema CLI injection is enabled
- whether the engine uses canonical passthrough or compat translation
- whether prompt injection uses canonical or compat summary
- whether parsed payloads need canonicalization

Why:
- The adapter profile already governs prompt/session/workspace behavior.
- Structured-output transport policy is engine capability metadata, not per-run orchestration policy.

Alternatives considered:
- Add new run-time overrides for schema mode.
  Rejected because the current problem is governance drift, not per-run experimentation.
- Infer strategy implicitly from engine name in code.
  Rejected because that would preserve hidden branching instead of declaring capability.

### Decision 3: Canonical schema stays SSOT; compat artifacts are derived transport assets

Canonical `.audit/contracts/target_output_schema.json` and `.md` remain the SSOT. If an engine cannot consume the canonical transport shape, runtime may materialize engine-specific compatibility artifacts such as:

- `.audit/contracts/target_output_schema.codex_compatible.json`
- `.audit/contracts/target_output_schema.codex_compatible.md`

Why:
- It preserves a stable machine-truth contract for audit, repair, and future engines.
- It avoids contaminating the canonical contract with one engine's schema subset limitations.

Alternatives considered:
- Relax the canonical schema to match Codex's subset.
  Rejected because canonical SSOT must describe the true final/pending contract, not one transport limitation.
- Generate compat schema in-memory only.
  Rejected because run-scoped artifacts aid auditability and keep CLI/prompt decisions inspectable.

### Decision 4: Prompt contract selection and CLI schema selection must come from the same resolver

The same pipeline resolver determines both:

- the machine schema artifact consumed by the engine CLI
- the prompt-facing summary artifact injected into `SKILL.md`

Why:
- Codex compat transport is only safe if the agent sees the same contract shape that the CLI enforces.
- This prevents a recurring failure mode where prompt text describes canonical union output but the CLI enforces a translated compat schema.

Alternatives considered:
- Keep prompt summary generation in the patcher and machine schema selection in command builders.
  Rejected because that is exactly the split-brain model this change is fixing.

### Decision 5: Payload canonicalization runs in the shared adapter runtime after parse

Parsed payload canonicalization happens in the shared adapter runtime path, after engine parsing and before the final `AdapterTurnResult` is returned to orchestration.

Why:
- The runtime adapter already has access to `run_dir`, `options`, and the adapter profile.
- This keeps orchestration and downstream lifecycle code unaware of engine transport shims.

Alternatives considered:
- Canonicalize inside engine parsers.
  Rejected because parsers should stay focused on extracting engine rows, not on run-scoped artifact policy.
- Canonicalize later in orchestrator services.
  Rejected because that would expose compat transport shape too far up the stack.

## Risks / Trade-offs

- [Risk] The pipeline becomes a new shared hotspot for engine-specific behavior.  
  Mitigation: keep the fixed pipeline surface small and make non-participating engines explicit noops.

- [Risk] Compat prompt summaries may still underspecify some business fields if the translator is too lossy.  
  Mitigation: keep canonical schema as SSOT, materialize compat artifacts on disk, and extend compat-summary tests together with translator evolution.

- [Risk] Profile-driven strategy can drift from actual engine capability if adapter profiles are edited casually.  
  Mitigation: validate profiles fail-fast and cover strategy fields with targeted command/pipeline tests.

- [Risk] Derived compat artifacts may be mistaken for canonical truth by future contributors.  
  Mitigation: specs and docs must state that compat artifacts are transport/audit assets only and must not replace canonical artifacts.
