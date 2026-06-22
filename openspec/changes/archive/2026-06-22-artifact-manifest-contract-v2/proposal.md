# Artifact Manifest Contract V2

## Why

Artifact manifest semantics are currently encoded through the reserved role string `x-role: "artifact-manifest"`. That makes `x-role` carry type semantics even though roles are intended to be free-form labels. The runtime should instead use `x-type: "artifact-manifest"` as the canonical manifest marker.

Agents may also generate manifest entries as absolute paths while working with local tools. The runtime needs to accept workspace-local absolute manifest entries, validate them, and normalize the persisted manifest back to workspace-relative paths before result projection and bundling.

## What Changes

- Add `x-type: "artifact-manifest"` as the only semantic marker for generated artifact manifests.
- Keep `x-role` as a free-form role string; `x-role: "artifact-manifest"` has no special semantics.
- Allow artifact manifest values to be workspace-relative paths or absolute paths inside the workspace.
- Rewrite artifact manifest contents to workspace-relative POSIX paths during terminal artifact resolution.
- Keep `result.json.artifacts` and bundle entries workspace-relative only.

## Out of Scope

- Moving or copying workspace-external files referenced from artifact manifests.
- Changing ordinary artifact path behavior for `x-type: "artifact"` or `x-type: "file"`.
