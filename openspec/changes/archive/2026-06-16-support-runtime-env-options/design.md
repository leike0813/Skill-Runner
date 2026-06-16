## Context

Runtime options are persisted in the request store, mirrored into request input audit snapshots, and used again for upload, retry, resume, and recovery paths. Raw environment values may be sensitive and must not be written to those durable public surfaces. At the same time, queued and resumed runs need the original values after process restart.

## Goals / Non-Goals

**Goals:**
- Accept `runtime_options.env` as a flat object of env variable names to string values.
- Validate names, values, count, and disallowed base variables before execution.
- Persist raw values in a local secret vault with restrictive file permissions.
- Persist only redacted env projections in DB, status/detail responses, input manifests, and audit files.
- Apply env values only to the current adapter subprocess and dependency probe environment.
- Support queued/retry/resume after backend restart.

**Non-Goals:**
- Adding KMS/encrypted secret storage.
- Adding env to cache keys.
- Allowing clients to override process identity/path/runtime bootstrap variables.
- Writing env into engine profile/home/settings files.

## Decisions

1. **Use `runtime_options.env` as the only public field.**  
   The field shape is `{"NAME": "value"}`. It is available to installed and temp-upload jobs.

2. **Persist a redacted projection in normal records.**  
   Before creating the request record, raw values are validated and saved to the vault. The request payload replaces `env` with `{ "NAME": {"redacted": true} }`, preserving visibility that a variable was declared without exposing the value.

3. **Use a local per-request vault.**  
   Raw env is stored at `data/run_secrets/<request_id>.env.json`. The directory is created with mode `0700`, files are written with mode `0600`, and cleanup removes the file when its request/run records are deleted.

4. **Inject through internal run options.**  
   Attempt preparation reads the vault when a redacted env projection is present and injects `__runtime_env` into run options. The base adapter overlays `__runtime_env` after engine profile env construction and before command normalization, dependency probing, uv wrapping, and subprocess creation.

5. **Fail fast when a required secret is missing.**  
   If persisted runtime options declare env but the vault file is missing or invalid, preparation raises `RUNTIME_ENV_SECRET_MISSING`, which the orchestrator turns into a failed run.

6. **Keep cache stable across env changes.**  
   Env is intentionally excluded from cache key construction. Callers that expect env to affect outputs must set `runtime_options.no_cache=true`.

## Risks / Trade-offs

- [Risk] Clients may forget `no_cache=true` for env-influenced outputs. Mitigation: document the behavior explicitly.
- [Risk] Local vault is not encrypted. Mitigation: restrictive filesystem permissions and a narrow service boundary; encrypted storage remains a future replacement.
- [Risk] Existing internal code may revalidate redacted persisted options. Mitigation: options policy accepts the canonical redacted projection while raw values are accepted only as strings at ingress.
