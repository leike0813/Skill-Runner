Forensic or one-off utility scripts live here.

These scripts are intentionally not part of the supported runtime/deployment surface.

## chat_replay_to_markdown.py

Render a `chat_replay.jsonl` audit stream as a human-readable Markdown transcript:

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/chat_replay_to_markdown.py \
  data/workspaces/<run-id>/.audit/<namespace>/chat_replay.jsonl \
  --full \
  -o data/workspaces/<run-id>/.audit/<namespace>/chat_replay.md
```

## probe_codebuddy.py

Capture CodeBuddy CLI evidence in an ignored `data/codebuddy_probes/<timestamp>/`
directory. The default cases only inspect local CLI metadata and replay existing
captures; they do not start an agent turn.

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/probe_codebuddy.py
```

Agent cases require an explicit opt-in and dedicated credentials. Supply a
credential through one of the probe-only environment variables rather than the
shell command line; the script records only its presence and digest.

```bash
SKILL_RUNNER_CODEBUDDY_PROBE_API_KEY='...' \
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/probe_codebuddy.py \
  --allow-agent-cases \
  --network-environment internal \
  --cases explicit-credential materialization structured-json structured-stream tool-event resume cancel concurrency
```

Use `--update-investigation` only after reviewing the generated, sanitized
`summary.json`; it appends a summary to the CodeBuddy investigation artifact.

For a deliberate diagnostic of the operating-system credential manager while
keeping `HOME` and `CODEBUDDY_CONFIG_DIR` isolated, add `--allow-host-login`.
This is never enabled by default and should not be combined with a production
credential rotation or a broad probe run.

If that isolated check shows that CodeBuddy also needs its normal configuration
state, add `--use-host-state` together with `--allow-host-login`. Host state is
not copied into evidence or directory snapshots; this mode may create ordinary
CodeBuddy logs in the host configuration directory.

The `helper-credential` case additionally requires
`SKILL_RUNNER_CODEBUDDY_PROBE_HELPER_SECRET` to contain the helper's expected
credential. It is used only to redact the captured streams and is never passed
to CodeBuddy or written to evidence.

### SDK-derived `AUTH_TOKEN` probe

The `sdk-auth-token` case is an explicit, one-off forensic check of whether
the official Python SDK can obtain a token from an already logged-in host and
whether that token alone can authenticate an isolated CLI process. Install the
SDK only in the approved shared forensic environment:

```bash
uv pip install --python "$HOME/.ar/.venv/bin/python" codebuddy-agent-sdk
```

Then run it with both agent execution and host-login access explicitly enabled:

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/probe_codebuddy.py \
  --allow-agent-cases \
  --allow-host-login \
  --cases sdk-auth-token
```

The case obtains the SDK result in a restricted host environment, records only
the presence, length, and digest of its token, and passes the raw value in
memory to a CLI child with fresh `HOME`, XDG, and `CODEBUDDY_CONFIG_DIR`
directories. It also captures a no-token control and an invalid-`AUTH_TOKEN`
host-state control. It never prints or writes the token, user profile, or login
URL, and scans the final evidence tree for accidental token persistence.

This is not a production authentication route. It intentionally reads the host
login state and does not validate expiry, refresh, revocation, or OAuth Client
Credentials. Do not use it in a service runtime.

### SDK token lifecycle metadata

`sdk-token-lifecycle` acquires the already-authorized host token twice without
printing it. It records only whether the token rotated, JWT time claims, TTL,
and evidence-leak scan results. It does not regard an unsigned JWT payload as
an authorization decision and does not test actual expiry or revocation.

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/probe_codebuddy.py \
  --allow-agent-cases \
  --allow-host-login \
  --network-environment internal \
  --cases sdk-token-lifecycle
```

### Direct-pipe replay of documented samples

`document-sample-1` and `document-sample-2` execute the prompts recorded in
the investigation artifact and capture CodeBuddy stdout directly from the
subprocess pipe. They do not copy terminal output. The second case creates a
new session ID and performs the documented four-turn `-r` sequence.

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/probe_codebuddy.py \
  --allow-agent-cases \
  --allow-host-login \
  --use-host-state \
  --cases document-sample-1 document-sample-2
```

Use `stdout_protocol_summary.framing.repaired_newlines` together with a
byte-level scan of `stdout.raw` to determine whether a physical newline really
occurred inside a JSON string. Historical copied JSONL samples are recovery
inputs, not proof of a current native CLI framing defect.

### Service configuration isolation and resume

`service-config-isolation` uses the authorized host login only to obtain an
in-memory SDK token. Every actual CLI subprocess then runs with a new service
`HOME` and one shared, service-owned `CODEBUDDY_CONFIG_DIR`. It verifies
project-settings inclusion versus planted user-settings exclusion, a fresh
subprocess `-r` resume, two concurrent sessions, and token absence from the
service config and evidence root.

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/probe_codebuddy.py \
  --allow-agent-cases \
  --allow-host-login \
  --cases service-config-isolation
```

The case is evidence only: it does not make host login a runtime dependency.
It does not simulate a full Skill Runner server restart or sustained concurrent
load.

### SDK interactive login from a clean state

`sdk-interactive-auth` starts the SDK with a wholly new temporary home,
configuration, and XDG state. It prints a one-time URL only to the terminal,
waits for an operator to complete login, then verifies the returned token in a
second fresh CLI state. It is disabled unless both network execution and
interactive login are explicitly allowed:

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/probe_codebuddy.py \
  --allow-agent-cases \
  --allow-interactive-login \
  --network-environment internal \
  --cases sdk-interactive-auth
```

According to the official environment-variable reference, `internal` is the
China edition and `ioa` is the iOA enterprise edition; omit
`--network-environment` for the public route. The URL is never persisted in
the evidence directory. The harness records only callback success/failure
shape, token length/digest, and token-occurrence counts. It scans the SDK and
CLI temporary states before automatic cleanup, then separately scans the
evidence root. A token written into the SDK temporary state is a significant
result: it must be removed as part of any future interactive-auth workflow.
