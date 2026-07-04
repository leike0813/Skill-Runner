# Runtime Preamble Options

`runtime_options.preamble_prompt` lets a client provide bounded run-scoped context for one run:

```json
{
  "runtime_options": {
    "preamble_prompt": "Use the uploaded bibliography as additional context."
  }
}
```

The preamble is not a system prompt override. It is inserted after the skill invoke line and before the skill body prompt, inside a fixed section that states it cannot override service, engine, skill, safety, tool, or output-schema instructions.

## Validation

`runtime_options.preamble_prompt` must be a string.

- Leading and trailing whitespace is trimmed.
- CRLF and CR newlines are normalized to LF.
- The normalized value must be non-empty.
- The normalized value may contain at most 8000 characters.
- NUL and C0 control characters are rejected, except LF and tab.

Persisted runtime options may contain only the internal redacted descriptor shape:

```json
{
  "preamble_prompt": {
    "redacted": true,
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "length": 42
  }
}
```

## Persistence And Redaction

Raw preamble values are stored only in the local secret vault:

```text
data/run_secrets/<request_id>.preamble.json
```

The vault directory is created with `0700` permissions and each preamble file with `0600` permissions on platforms that support POSIX modes.

Normal DB records, status/detail APIs, input manifests, audit snapshots, and bundles contain only the redacted descriptor. They must not contain the raw preamble text.

## Injection

The raw preamble is restored during attempt preparation only when:

- the attempt number is `1`;
- the attempt is the initial run invocation;
- no internal prompt override or resume/repair option is active.

Retry attempts, interactive replies, auth resumes, recovery resumes, and output repair reruns do not receive the preamble again.

## Cache Behavior

The normalized preamble content hash participates in cache key construction. Two otherwise identical auto runs with different preambles must not share a cache entry.

`runtime_options.env` remains excluded from the cache key.
