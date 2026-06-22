# Design

## Contract Shape

`artifact-manifest` is now a first-class `x-type`. Runtime manifest expansion is keyed only by `x-type: "artifact-manifest"`. `x-role` remains a free-form label and has no special behavior, including when its value is `"artifact-manifest"`.

Ordinary artifact fields keep their existing behavior:

- `x-type: "artifact"` resolves one output file and requires a non-empty `x-role`.
- `x-type: "artifact-manifest"` resolves a manifest file, expands its flat object values, and requires a non-empty `x-role`.
- `x-type: "file"` resolves one output file for compatibility.

## Manifest Path Normalization

During terminal artifact resolution, the runtime reads artifact manifest JSON and validates each value as either:

- a safe workspace-relative path, or
- an absolute path whose resolved target is inside the workspace.

Each valid value is normalized to a workspace-relative POSIX path. If every entry is valid and any value changed, the runtime rewrites the manifest file before `result.json` projection and bundle assembly. Workspace-external absolute paths are invalid and are not moved into the workspace.

## Failure Behavior

Invalid manifest shape, unreadable JSON, non-string values, missing files, directories, invalid relative paths, and workspace-external absolute paths continue to fail terminal normalization with `BUNDLE_ASSEMBLY_*` diagnostics. Bundle assembly still consumes only `result.json.artifacts`, which remains workspace-relative.
