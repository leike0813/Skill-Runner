## Context

Runtime skill materialization already copies installed or temporary skills into a run-local snapshot, then applies modular `SKILL.md` patches through `SkillPatcher`. Namespaced result paths are persisted in run records and exposed as `__result_json_path` during execution. Normal bundles are contract-driven and currently include result files plus files listed in `result.json.artifacts`.

The feedback sidecar must remain outside the business output schema and result JSON, so bundle inclusion cannot depend on `result.json.artifacts`.

## Goals / Non-Goals

**Goals:**
- Add an opt-in runtime option with strict boolean validation.
- Keep default behavior unchanged when the option is missing or false.
- Inject the requested Markdown block, rendered with the actual feedback path, at the very end of run-local `SKILL.md`.
- Keep cache semantics explicit by including a feedback token only when the option is true.
- Diagnose sidecar state on successful terminal runs without affecting final status.
- Include present sidecars in normal bundles next to their corresponding result file.

**Non-Goals:**
- Backend-generated feedback.
- A dedicated API to read feedback sidecars.
- Output schema or `result.json` changes.
- Run-root instruction injection.
- Forcing cache bypass.

## Decisions

1. **Runtime option shape.**  
   The public key is `runtime_options.collect_skill_run_feedback`. It is optional, defaults to false, and must be a boolean when present.

2. **Cache key token.**  
   `compute_cache_key` accepts a `collect_skill_run_feedback` boolean. It adds `"skill_run_feedback": "collect_v1"` only when true, preserving equality between missing and false.

3. **Patch layer.**  
   `RunFolderBootstrapper` receives `collect_skill_run_feedback` and the actual result-local feedback path from create/upload flows, then passes both to `SkillPatcher`. `SkillPatcher` renders `patch_skill_run_feedback.md.j2` with `feedback_path` and appends the optional section after the existing Execution Mode section. The section marker is `## Skill Run Feedback Sidecar`.

4. **Sidecar diagnostics.**  
   `RunAttemptProjectionFinalizer` checks `result_path.parent / "_skill_run_feedback.md"` only for `RunStatus.SUCCEEDED`. Missing, empty, and read/stat failures are logged, but terminal status, cache recording, and bundle building continue.

5. **Bundle inclusion.**  
   `RunBundleService` appends `_skill_run_feedback.md` beside each selected result file when present and file-like. It does not add the path to `result.json.artifacts`.

## Risks / Trade-offs

- [Risk] A cached true run may reuse a previous feedback note. This follows the confirmed requirement that feedback participates in cache key but does not force `no_cache`.
- [Risk] Agent may ignore the patch or fail to write the sidecar. This is diagnostic-only and must not fail the run.
