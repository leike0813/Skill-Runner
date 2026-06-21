# Design: artifact manifest bundling

## Output Schema Contract

`x-type: "artifact"` now requires a non-empty `x-role`. Ordinary roles keep the current behavior: the output field value is resolved as one artifact path. The reserved role `artifact-manifest` declares that the field value points to a JSON manifest file.

The manifest file must be a flat JSON object. Keys are labels only. Values must be non-empty workspace-relative file paths. Absolute paths, empty paths, `.`/`..` segments, directories, missing files, nested objects, arrays, and non-string values are invalid.

## Runtime Resolution

Terminal output normalization resolves ordinary artifact fields exactly as before. For an `artifact-manifest` field, normalization first resolves and rewrites the manifest file path, then reads the manifest and appends both the manifest path and every manifest value path to the terminal `artifacts` list. Manifest value paths are not moved or rewritten; they must already be valid workspace-relative paths so bundle entries match the JSON strings.

Invalid manifest assembly produces `BUNDLE_ASSEMBLY_*` warning codes and terminal validation errors. The run fails instead of producing an incomplete bundle.

## Bundle Assembly

Bundle generation treats `result.json.artifacts` as an assembly contract. Every listed artifact path must be a valid workspace-relative file. Invalid or missing entries raise a structured `BundleAssemblyError` with code, message, and optional path details. Lazy bundle download converts that error to an HTTP diagnostic instead of an unstructured 500.

## Documentation

File protocol and API docs describe the manifest shape, path rules, and diagnostic codes. Skill author docs show ordinary artifacts with explicit roles and reserve `artifact-manifest` for generated path manifests.

