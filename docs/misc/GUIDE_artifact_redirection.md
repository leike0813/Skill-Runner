# Artifact Redirection Template — Integration Guide

## Overview

`patch_artifact_redirection.md` is a Markdown template containing the artifact path redirection prompt. It contains a placeholder `{artifact_lines}` that must be populated at runtime by `SkillPatcher`.

## Template Content

```markdown
---

# Runtime Output Overrides

The following output artifacts MUST be written to the specific paths listed below.
IMPORTANT: Ignore any previous instructions regarding the file paths of these outputs.

{artifact_lines}

Ensure you do NOT write these files to the current directory or any other location. Use ONLY the paths listed above.
When reporting these artifacts in your final JSON output, use the exact paths listed above as the field values.
```

## Placeholder: `{artifact_lines}`

This placeholder is replaced at runtime with one line per artifact, using the format:

```
- <role> (<pattern>) -> {{ run_dir }}/artifacts/<pattern>
```

Where:
- `role` and `pattern` come from each `ManifestArtifact` object (fields: `.role`, `.pattern`).
- `{{ run_dir }}` is a **literal string** written into the SKILL.md as-is. It is NOT resolved by Jinja2 at this stage. The agent CLI's Jinja2 rendering may resolve it later when building the prompt, or the agent may interpret it contextually.

### Example Generated Output

Given artifacts:
```python
[
    ManifestArtifact(role="digest", pattern="digest.md"),
    ManifestArtifact(role="references", pattern="references.json"),
]
```

The `{artifact_lines}` placeholder is replaced with:
```
- digest (digest.md) -> {{ run_dir }}/artifacts/digest.md
- references (references.json) -> {{ run_dir }}/artifacts/references.json
```

## Required Changes to `SkillPatcher`

### Current Implementation (to be replaced)

The current `generate_artifact_patch` method (lines 35–53) builds the entire patch text inline using `patch_lines`:

```python
def generate_artifact_patch(self, artifacts: List[ManifestArtifact]) -> str:
    if not artifacts:
        return ""
    patch_lines = [
        "\n",
        "---",
        "# Runtime Output Overrides",
        "Please write the following outputs to these specific paths:",
        "IMPORTANT: Ignore any previous instructions regarding the file paths of these outputs.",
    ]
    for artifact in artifacts:
        target_path = "{{ run_dir }}/artifacts/" + artifact.pattern
        patch_lines.append(f"- {artifact.role} ({artifact.pattern}) -> {target_path}")
    patch_lines.append(
        "\nEnsure you do NOT write these files to the current directory, but specifically to the paths above."
    )
    return "\n".join(patch_lines)
```

### New Implementation

1. **Add a template path** in `__init__`, similar to the existing `_completion_contract_path`:

```python
self._artifact_redirection_template_path = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "templates"
    / "patch_artifact_redirection.md"
)
```

2. **Add a template loader** method:

```python
def _load_artifact_redirection_template(self) -> str:
    path = self._artifact_redirection_template_path
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"artifact redirection template is missing: {path}")
    return path.read_text(encoding="utf-8").strip()
```

3. **Rewrite `generate_artifact_patch`** to load the template and fill the placeholder:

```python
def generate_artifact_patch(self, artifacts: List[ManifestArtifact]) -> str:
    if not artifacts:
        return ""
    template = self._load_artifact_redirection_template()
    lines = []
    for artifact in artifacts:
        target_path = "{{ run_dir }}/artifacts/" + artifact.pattern
        lines.append(f"- {artifact.role} ({artifact.pattern}) -> {target_path}")
    artifact_lines = "\n".join(lines)
    return template.replace("{artifact_lines}", artifact_lines)
```

### Key Points

- The marker `ARTIFACT_PATCH_MARKER = "# Runtime Output Overrides"` remains unchanged. It is present in the template file and used by `_append_patch_if_missing` for idempotency.
- No other methods or callers need to change. `generate_artifact_patch` still returns a `str` and is consumed by `patch_skill_md` and `generate_patch_content` as before.
- The `{artifact_lines}` placeholder uses single curly braces (Python `str.replace`), NOT Jinja2 `{{ }}` syntax, to avoid confusion with the literal `{{ run_dir }}` in the artifact path.
