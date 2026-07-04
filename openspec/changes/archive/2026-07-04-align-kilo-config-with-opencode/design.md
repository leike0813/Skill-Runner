# Design

Kilo config compatibility is field-level, not file-identity-level. The implementation reuses OpenCode-compatible `provider`, `permission`, `skills`, and tool config semantics, while preserving Kilo's schema URL, `.kilo/kilo.jsonc` target, and Kilo model defaults.

The existing Kilo composer already implements the desired layer order and rejects user/skill MCP roots. No composer behavior change is needed; the change is confined to profile-declared assets and schema validation.
