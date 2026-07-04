# Design

`preamble_prompt` is treated as client-provided run context, not as a system prompt override. The raw text is validated, normalized, hashed, and stored in request-scoped secret storage. Persisted request JSON uses a descriptor containing only `redacted`, `sha256`, and `length`.

Execution preparation resolves the raw secret only for the first initial attempt. Resume attempts for interaction replies, auth continuations, recovery, retries, and output repair do not receive the internal preamble option. The common prompt builder wraps the preamble between stable boundaries after the invoke line and before the skill body.

Cache keys receive `preamble_prompt_hash` explicitly. This avoids making unrelated runtime options cache-affecting while still making preamble-sensitive outputs cache-safe.
