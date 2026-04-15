## Design Summary

Prompt assembly keeps the invoke-line-first model but narrows the body path:

1. Render the invoke line from `prompt_builder.skill_invoke_line_template`.
2. Resolve a skill-authored full body override from `entrypoint.prompts[engine]` or `.common`.
3. If no skill-authored body exists, render the shared default body template.
4. Wrap the shared default body template with optional `body_prefix_extra_block` and `body_suffix_extra_block`.

This makes the adapter profile describe only two things:

- how the engine invokes the skill
- whether the engine needs an extra declaration before or after the shared default body

## Key Decisions

### Shared default body template

The default body is a single static template under `server/assets/templates/prompt_body_common.j2`. It renders:

- `# Inputs`
- `# Parameters`
- the stable execution sentence

Per-engine cloned body templates are removed.

### No hidden compatibility layer

This change is intentionally breaking. Prompt builder no longer injects:

- `params_json`
- `input_prompt`
- `input_file`
- `skill_dir`

It also removes:

- `parameter.prompt` runtime body sourcing
- merge-input-into-parameter compatibility behavior
- inline fallback body selection

Any skill prompt still depending on those variables must be migrated explicitly.

### Claude special case

Claude keeps its sandbox-specific guidance, but it now lives in `body_prefix_extra_block` rather than a dedicated default template file.
