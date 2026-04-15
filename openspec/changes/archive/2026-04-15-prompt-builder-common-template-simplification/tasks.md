## 1. Implementation

- [x] 1.1 Replace per-engine default body templates with one shared prompt body template plus optional profile prefix/suffix extra blocks.
- [x] 1.2 Simplify `prompt_builder` schema/loader/runtime wiring to the new field set and remove legacy body compatibility switches.
- [x] 1.3 Update engine adapter profiles, affected fixture prompts, and prompt-builder docs to the new breaking contract.

## 2. Validation

- [x] 2.1 Update prompt-builder and adapter-profile unit tests for the new schema and default body behavior.
- [x] 2.2 Run targeted pytest coverage for prompt builder and profile loader changes.
- [x] 2.3 Run mypy for the touched runtime adapter modules.
