# Runtime Env Options

`runtime_options.env` lets a client inject environment variables for one run:

```json
{
  "runtime_options": {
    "env": {
      "FOO": "value"
    }
  }
}
```

The injected values are local to the adapter subprocess for that run. They are applied after the engine profile builds its subprocess environment and before dependency probes, uv wrapping, and process creation. Skill Runner does not mutate `os.environ` and does not write these values into engine homes, profiles, or settings files.

## Validation

`runtime_options.env` must be an object.

- Variable names must match `^[A-Z_][A-Z0-9_]{0,127}$`.
- Values must be strings; empty strings are allowed.
- A single value may contain at most 8192 characters.
- A request may define at most 64 variables.
- The following base variables cannot be overridden: `PATH`, `HOME`, `SHELL`, `PWD`, `OLDPWD`, `USER`, `USERNAME`, `LOGNAME`, `TMPDIR`, `TEMP`, `TMP`, `VIRTUAL_ENV`, `CONDA_PREFIX`, `PYTHONPATH`, `LD_LIBRARY_PATH`.

### CodeBuddy Reserved Variables

For `engine=codebuddy`, callers may add ordinary run-local variables but must not override `CODEBUDDY_AUTH_TOKEN`, `CODEBUDDY_API_KEY`, `CODEBUDDY_INTERNET_ENVIRONMENT`, `CODEBUDDY_BASE_URL`, or `CODEBUDDY_CONFIG_DIR`. The adapter clears inherited CodeBuddy credential and routing variables, then injects only the selected canonical provider's vault token, provider environment, and persistent provider config directory. This keeps domestic (`codebuddy-cn`) and international (`codebuddy-global`) routing isolated.

## Persistence And Redaction

Raw env values are stored only in the local secret vault:

```text
data/run_secrets/<request_id>.env.json
```

The vault directory is created with `0700` permissions and each env file with `0600` permissions on platforms that support POSIX modes.

Normal DB records, status/detail APIs, input manifests, audit snapshots, and bundles contain only a redacted projection such as:

```json
{
  "env": {
    "FOO": {
      "redacted": true
    }
  }
}
```

If a queued, retried, or resumed run declares env but the vault file is missing, the run fails with `RUNTIME_ENV_SECRET_MISSING`.

## Cache Behavior

`runtime_options.env` does not participate in cache key construction. Callers that expect env values to affect output must set `runtime_options.no_cache=true`.

The same rule applies to CodeBuddy account identity: cache reuse is caller-controlled and a matching cached result is not automatically invalidated when a provider credential changes. Set `no_cache=true` when the selected account is material to the result.

## Cleanup

Expired run cleanup and manual `/v1/jobs/cleanup` remove matching env secret files.

## Zotero Bridge Usage

Zotero Bridge connection values are request-scoped env values. The managed deployment supplies `ZOTERO_BRIDGE_PROFILE` and `ZOTERO_BRIDGE_BIN`; callers pass `ZOTERO_BRIDGE_ENDPOINT`, `ZOTERO_BRIDGE_TOKEN`, and optionally `ZOTERO_BRIDGE_CONNECTION_MODE` through `runtime_options.env`.

The token is treated like any other runtime env secret: raw values stay in the vault and are not exposed through DB records, status/detail APIs, audit files, or bundles.
