# Proposal: add artifact manifest bundling

## Summary

Output artifact contracts currently resolve each `x-type: artifact|file` field as one file path and store the resolved paths in terminal `result.json.artifacts`. Some skills need to emit a generated artifact manifest that lists a variable set of final files. This change adds a contract role for that manifest and makes bundle assembly fail with explicit diagnostics when declared artifact paths cannot be assembled.

## Problem

The output schema contract has no way to distinguish an ordinary artifact path from a manifest of artifact paths. Bundle generation also skips missing artifact entries silently, which can produce an incomplete zip while the run still appears successful.

## Goals

- Require `x-type: "artifact"` fields to declare an explicit `x-role`.
- Add `x-role: "artifact-manifest"` for a JSON object mapping names to workspace-relative file paths.
- Expand artifact-manifest contents into terminal `result.json.artifacts` so bundle entries remain workspace-relative and match JSON path values.
- Return clear `BUNDLE_ASSEMBLY_*` diagnostics for invalid, missing, or non-bundleable paths.

## Non-Goals

- Do not add HTTP endpoints.
- Do not change zip entry naming.
- Do not support nested artifact manifests or arrays.
- Do not change `x-type: "file"` compatibility behavior.

