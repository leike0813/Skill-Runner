## Context

Kilo Code is installed as `@kilocode/cli` and exposes a native binary through `kilo` and `kilocode`. Local probes confirmed:

- `kilo run --format json --auto` emits JSONL events with top-level `type`, `timestamp`, `sessionID`, and `part` or `error`.
- `--session <sessionID>` resumes the same session.
- `type:error` events can represent failures even when the process exits with code `0`.
- `kilo models --verbose` is the intended model probe surface for phase 1.
- Kilo uses XDG-aware config/data/cache directories, while project-level run config should be written to `.kilo/kilo.jsonc`.

## Design Decisions

1. **Profile-driven Kilo engine**
   `kilo` is added to the same profile-driven adapter architecture as other active engines. Kilo-specific command, parser, config, model-probe, and auth-pattern logic lives under `server/engines/kilo/**`; shared modules only register the engine or consume profile-declared data.

2. **Project-level Kilo config**
   Runtime config is written to `run_dir/.kilo/kilo.jsonc` using JSON content. Standard JSON is valid JSONC, so phase 1 does not add a JSONC writer.

3. **Shared config layering**
   Kilo uses `engine_default -> skill defaults -> runtime kilo_config -> model overlay -> governed MCP -> enforced`. User and skill config roots `mcp` and `provider` are blocked in phase 1. Governed MCP is the only source allowed to write Kilo `mcp`.

4. **Runtime model probe**
   Kilo model catalog uses runtime probe mode. The probe runs `kilo models --verbose`, parses available model records, caches last-known-good results through the existing model catalog lifecycle, and falls back to `kilo/kilo-auto/free` if no cache exists.

5. **Auth deferred, error detection retained**
   Kilo does not expose startable auth sessions in phase 1. The auth strategy declares disabled/no-start semantics, while parser auth patterns still identify runtime auth failures such as `PAID_MODEL_AUTH_REQUIRED`, 401/403, and Kilo Gateway unauthenticated messages.

## Architecture

### Execution Adapter

`KiloExecutionAdapter` composes:

- `KiloCommandBuilder`
- `KiloConfigComposer`
- `KiloStreamParser`
- `ProfiledPromptBuilder`
- `ProfiledSessionCodec`
- `ProfiledAttemptRunFolderValidator`

The Kilo command builder resolves the managed command from `AgentCliManager` and applies profile defaults. Start and resume command shapes are:

```text
kilo run --format json --auto --model <model> <prompt>
kilo run --format json --auto --session <sessionID> --model <model> <prompt>
```

### Parser

The parser reads JSONL rows from stdout. It extracts:

- session id from top-level `sessionID`
- assistant text from `type=text` and `part.text`
- final metadata from `type=step_finish`
- failure diagnostics from `type=error`

Any `type=error` row produces a failed turn result independent of process exit code.

### Config

The composer writes `run_dir/.kilo/kilo.jsonc`. It preserves Kilo-native config fields allowed in phase 1 and rejects `provider` roots until third-party provider support is explicitly designed.

### Model Catalog

Kilo has an engine-local model catalog probe service. The shared lifecycle adds a Kilo handler that calls the Kilo service without embedding Kilo parsing rules in shared code.

### Management

Kilo is added to engine keys, adapter registry, managed install/upgrade, bootstrap fallback, status cache, UI metadata, and schema enums. The UI exposes install/status/model selection but no Kilo auth actions in phase 1.

## Failure Handling

- CLI missing: clear runtime error, no fallback to unrelated engines.
- Probe failure: use last-known-good cache; if absent, return `kilo/kilo-auto/free`.
- JSONL parse failure: return a parser failure turn result with diagnostics.
- Kilo auth error JSONL: map to auth signal/failure, even if exit code is `0`.
- Secret risk: redact API-key-like values from Kilo config validation/log output.

## Future Work

- `kilo auth login` delegated/browser flow.
- Kilo Gateway `KILO_API_KEY` management.
- Gateway BYOK observability.
- Third-party `provider.*` config and UI support.
- Richer model capability normalization from verbose probe metadata.
