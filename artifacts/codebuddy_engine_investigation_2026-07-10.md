# CodeBuddy Engine Investigation

Date: 2026-07-10

## Purpose and Scope

This note records the pre-implementation investigation for adding [CodeBuddy Code](https://www.codebuddy.cn/docs/cli/overview) as a Skill Runner engine. It covers CLI configuration, run-workspace materialization, authentication, session continuity, and stdout parsing.

The recommendations below are an implementation boundary for a future OpenSpec change. They do not modify runtime code, public APIs, or the active engine set.

## Evidence and Version Caveat

### Local installation

Observed on 2026-07-10:

- Package: `@tencent-ai/codebuddy-code`
- Binaries: `codebuddy`, `cbc`
- Version: `2.118.2`
- `codebuddy`: `/home/joshua/.nvm/versions/node/v24.12.0/bin/codebuddy`
- `cbc`: `/home/joshua/.nvm/versions/node/v24.12.0/bin/cbc`

The package is installed with `npm install -g @tencent-ai/codebuddy-code`.

Running `--help` under a temporary `HOME` created a `.codebuddy/` directory containing logs, local storage, plugin metadata, and shell snapshots. This is a stateful CLI even when the requested command does not execute an agent turn.

### Model catalog is not a static contract

The initial authenticated probe exposed the following model IDs:

`hy3`, `glm-5.2`, `glm-5.1`, `glm-5.0`, `glm-5.0-turbo`, `glm-5v-turbo`, `glm-4.7`, `minimax-m3`, `minimax-m2.7`, `kimi-k2.7`, `kimi-k2.6`, `kimi-k2.5`, `deepseek-v4-pro`, `deepseek-v4-flash`, and `deepseek-v3-2-volc`.

However, `codebuddy --help` from the same local version later advertised a different set, including `gpt-5.5`, `gpt-5.4`, `gpt-5.3-codex`, and Gemini variants. The difference may be account, endpoint, network-environment, or rollout dependent; this investigation does not establish the cause.

**Decision:** do not add a pinned model manifest based on either list. A future engine must capture a runtime catalog together with CLI version, configured network environment, collection time, and raw probe output. The engine must reject a model only against that recorded runtime catalog, not against this document.

## CLI and Session Contract

The official headless contract is `codebuddy -p`, with `--output-format text|json|stream-json`; `stream-json` emits an init event, conversation events, and a terminal result event. It supports `-r <session-id>` for a specific session and `-c` for the most recent local session. See [Headless mode](https://www.codebuddy.cn/docs/cli/headless) and the [CLI reference](https://www.codebuddy.cn/docs/cli/reference).

### Recommended command shape

Use one fresh subprocess per Skill Runner attempt:

```shell
codebuddy -p --output-format stream-json --permission-mode bypassPermissions <prompt>
codebuddy -p --output-format stream-json --permission-mode bypassPermissions -r <session-id> <reply>
```

`-r <session-id>` is the only resume mechanism suitable for a request-bound Skill Runner interaction. Do not use `--continue`: it selects the most recent CLI-local session rather than the request's persisted engine handle.

The local multi-turn samples show that every resumed subprocess emits a new `system.init` row containing the same `session_id`; a parser must therefore accept repeated init events. The session handle should be captured from the first valid event carrying `session_id`, not only from the terminal result.

### Unsupported launch modes

The future adapter must not pass these CodeBuddy options:

- `--worktree` / `--worktree-branch` / `--tmux`: CodeBuddy creates and changes to a Git worktree, potentially copies local files, and manages branches. That conflicts with Skill Runner's existing run workspace. See [Git worktree support](https://www.codebuddy.cn/docs/cli/worktree).
- `--sandbox`, `--serve`, or `--acp`: each introduces a separate execution, network, or transport topology outside the adapter subprocess contract.
- `--continue`: see the request-scoping concern above.

## Configuration and Workspace Materialization

### Confirmed CodeBuddy behavior

- `CODEBUDDY_CONFIG_DIR` relocates CodeBuddy configuration and data files. See the [environment-variable reference](https://www.codebuddy.cn/docs/cli/env-vars).
- Settings are layered as user, project, project-local, and CLI settings. `--settings` accepts a JSON file or JSON value; `--setting-sources` selects the ordinary settings sources. See [settings configuration](https://www.codebuddy.cn/docs/cli/settings) and [permission configuration](https://www.codebuddy.cn/docs/cli/permissions).
- Project skills live at `.codebuddy/skills/<skill-name>/SKILL.md`. CodeBuddy supports both `AGENTS.md` and `CODEBUDDY.md`; the latter wins when both exist. See [Skills](https://www.codebuddy.cn/docs/cli/skills) and [Memory](https://www.codebuddy.cn/docs/cli/memory).

### Recommended materialization design

1. Allocate one service-owned `CODEBUDDY_CONFIG_DIR` under the Skill Runner agent home. Keep it stable across attempts so `-r <session-id>` can locate persisted session state. Do not point it at a run directory, which would make resume depend on ephemeral per-attempt state.
2. Launch with `cwd=run_dir`. Materialize the selected skill at `run_dir/.codebuddy/skills/<skill-id>/SKILL.md` and its assets beneath that skill directory, preserving CodeBuddy's project-skill discovery layout.
3. Materialize `run_dir/CODEBUDDY.md` as the engine-specific projection of the existing run-root instruction contract. Do not duplicate it in the `.codebuddy` tree, and do not rely on an unrelated host-project `AGENTS.md`.
4. Generate a run-owned settings payload, pass it through `--settings`, and restrict `--setting-sources` to the sources deliberately materialized for the run. The adapter must not silently import host-user or host-project policy, hooks, MCP configuration, skills, or model preferences.
5. Treat CodeBuddy's automatic `.codebuddy` protection and its project trust semantics as engine behavior, not as a replacement for Skill Runner's filesystem boundary.

The clean-state service-config probe confirmed that `--setting-sources project`
loads a controlled `.codebuddy/settings.json` while excluding deliberately
planted user settings at both `~/.codebuddy/settings.json` and
`CODEBUDDY_CONFIG_DIR/settings.json`. Its minimal generated CLI settings used
`{"disableAllHooks": true}`. Additional settings needed for production policy
remain an implementation decision.

## Authentication Boundary

### Confirmed authentication precedence

CodeBuddy documents these non-interactive credential sources, in descending priority:

1. `CODEBUDDY_AUTH_TOKEN`
2. `apiKeyHelper`
3. `CODEBUDDY_API_KEY`

`CODEBUDDY_INTERNET_ENVIRONMENT` selects the expected service environment: the
default is public, `internal` is the China edition, and `ioa` is the iOA
enterprise edition; `CODEBUDDY_BASE_URL` can override the endpoint. See
[identity and access management](https://www.codebuddy.cn/docs/cli/iam) and the
[environment-variable reference](https://www.codebuddy.cn/docs/cli/env-vars).

The official documentation says interactive credentials are stored in the operating system credential manager/keyring. Relocating `CODEBUDDY_CONFIG_DIR` therefore does not by itself prove isolation from a host login state.

### Recommended first-release boundary

Only support explicit service-side credentials injected into the subprocess environment:

- `CODEBUDDY_AUTH_TOKEN`, or
- `CODEBUDDY_API_KEY`, or
- a service-controlled `apiKeyHelper`.

The adapter should also inject the selected `CODEBUDDY_INTERNET_ENVIRONMENT` and, when applicable, `CODEBUDDY_BASE_URL`. It must neither read, import, nor claim to isolate host keyring credentials. Interactive host-login reuse is a later, separately designed authentication feature.

### SDK host-login token probe (2026-07-10)

The official Python SDK (`codebuddy-agent-sdk==0.3.205`) was installed only in
the shared forensic environment. Its `authenticate()` call was invoked with a
whitelisted host-login environment: host `HOME` and the desktop credential
manager transport were available, inherited `CODEBUDDY_*` credential variables
were removed, and no user data was recorded. It returned a resolved flow
without an `auth_url` and exposed a non-empty `userinfo.token` (length and
SHA-256 only are in the ignored evidence). The corresponding CLI was
`2.118.2`; evidence is `data/codebuddy_probes/20260710T101329Z/`.

The token was held only in memory and passed directly to a fresh CodeBuddy CLI
subprocess. That subprocess had a new `HOME`, `CODEBUDDY_CONFIG_DIR`, and XDG
configuration/data/cache/state directories; it had no host credential-manager
transport or host configuration path. The control without a token ended in
`result.is_error=true` and requested `/login`; the SDK-token control ended in
`result.success`. A host-state subprocess with a deliberately invalid
`CODEBUDDY_AUTH_TOKEN` instead returned a 401 `error_during_execution` result,
despite exit code `0`. This proves that `CODEBUDDY_AUTH_TOKEN` is accepted in
the isolated CLI environment and overrides an otherwise usable host login.

The SDK transport in this version builds its child environment by merging its
`env` argument over `os.environ`. It is therefore not a safe runtime isolation
primitive by itself. The forensic harness temporarily replaces its own process
environment before invoking the SDK; a future engine must continue to consume
only service-provided explicit credentials and must not import this host-login
acquisition route into the runtime.

The probe does **not** establish token expiry, refresh, revocation, concurrent
interactive login, or a service-owned acquisition route. In particular, OAuth
Client Credentials remains the intended server/CI route and needs dedicated
`client_id`/`client_secret` evidence before it can be implemented. See the
[official Python SDK documentation](https://www.codebuddy.cn/docs/cli/sdk-python).

### Interactive-token lifecycle and runtime injection (2026-07-10)

Two consecutive host-state SDK acquisitions in the China-edition environment
returned the same JWT (same digest and expiry) rather than minting a refreshed
access token. Its unsigned temporal payload reported an `iat`/`exp` interval
of 31,192,080 seconds (about 361 days). This is scheduling evidence only, not
cryptographic validation, but it establishes that SDK `authenticate()` is not
a refresh API. Interactive-auth lifecycle policy must therefore use the token
`exp` as an advisory renewal deadline and treat a CodeBuddy 401 terminal result
as an immediate reauthorization signal. Evidence:
`data/codebuddy_probes/20260710T120021Z/`.

Skill Runner already provides the correct injection boundary for a future
adapter: `runtime_options.env` persists raw values only in the local run secret
vault, restores them for the adapter subprocess without mutating global
`os.environ`, redacts normal records/audits/bundles, and fails a missing vault
entry with `RUNTIME_ENV_SECRET_MISSING`. The focused unit suite
`tests/unit/test_runtime_env_options.py` passed (8 tests) during this probe.
The CodeBuddy adapter should consume `CODEBUDDY_AUTH_TOKEN` solely through that
boundary and set `no_cache=true` when credentials can affect an observable run.

### SDK interactive acquisition from a clean state (2026-07-10)

`authenticate(environment="internal")` was then run with a new temporary
`HOME`, XDG tree, and `CODEBUDDY_CONFIG_DIR`; no host configuration or desktop
credential-manager transport was inherited. It emitted a one-time
`copilot.tencent.com` URL. After the operator completed China-edition CodeBuddy
authorization, the SDK received `auth_result_callback.success=true` and
returned a non-empty token. A distinct, fresh CLI state without that token
ended in `result.is_error=true`; injecting the in-memory result as
`CODEBUDDY_AUTH_TOKEN` produced `result.success`.

The SDK authentication state itself contained one exact token occurrence before
its `TemporaryDirectory` was removed. The fresh CLI state and the ignored
evidence root contained zero occurrences. This establishes that interactive
SDK acquisition is viable, but must be treated as a credential-persistence
workflow: use a dedicated temporary state directory, verify and remove it on
completion, and do not assume that setting `CODEBUDDY_CONFIG_DIR` alone
eliminates OS-keyring behavior. The successful evidence is
`data/codebuddy_probes/20260710T110406Z/`.

An earlier public (`www.codebuddy.ai`) attempt and an earlier China-edition
attempt both returned generic `auth_failed` after browser completion. The
later China-edition success proves the SDK/CLI protocol can work, but those
failures do not identify their cause; preserve the callback shape and selected
environment in future evidence rather than treating a browser completion as a
successful acquisition.

## Stdout Protocol and Parser Requirements

### Observed envelope

The samples use a Claude-like event envelope:

- `system.init` includes `session_id`, effective `cwd`, model, tools, permission mode, and MCP metadata.
- `assistant.message.content[]` contains `thinking`, `text`, and `tool_use` blocks.
- `user.message.content[]` contains `tool_result` blocks.
- `file-history-snapshot` and `ai-title` are auxiliary rows.
- `result` carries `subtype`, `is_error`, `session_id`, response text, timing, usage, and permission-denial information.

The event meanings are close enough to reuse the existing Claude parser's conceptual mappings, but not its implementation identity. The new adapter needs its own `codebuddy_stream_json` parser profile and fixtures.

### Historical framing anomaly; not reproduced by native-pipe probes

Two historical captured outputs contain literal physical newlines inside quoted string values:

- sample 1 splits a large `user.tool_result` payload across physical lines;
- sample 2 attempt 4 splits an `assistant.thinking` value across physical lines.

Consequently, line-by-line `json.loads` and `jq` stop at those records, losing subsequent events. Their provenance is now uncertain: they may be native CLI output from an earlier version or path, but may also have acquired line breaks while being copied from a terminal.

The exact documented Sample 1 prompt and Sample 2 four-turn sequence were re-run
on 2026-07-10 with CLI `2.118.2`, using a subprocess pipe that wrote stdout
bytes directly to ignored evidence (no terminal copy). Sample 1 produced 29
physical lines and 29 logical JSON events; Sample 2 produced 6 physical lines
and 6 logical JSON events on each of its four attempts. Across all five native
captures, the stateful scanner found zero physical newlines while inside a JSON
string, zero recovered newlines, and zero JSON parse errors. Evidence:
`data/codebuddy_probes/20260710T111313Z/` and
`data/codebuddy_probes/20260710T111523Z/`.

**Parser requirement:** treat ordinary native output as JSONL, but retain a
stateful recovery path for malformed historical or future streams. The recovery
path tracks quoted-string and escape state across physical lines, retains raw
byte offsets and original bytes for audit, and must never let a malformed row
erase later valid `result` or session events. Do not describe physical newlines
inside CodeBuddy JSON strings as a current, reproducible CLI defect without a
native-pipe capture for the exact version and environment.

The parser must use `result.is_error`, terminal subtype, subprocess exit status, and the presence of a valid terminal event together. A `result` row alone is not sufficient proof of a successful Skill Runner turn.

## Existing Capture Samples

### Sample 1: tool use and reasoning

```shell
codebuddy --output-format stream-json --permission-mode bypassPermissions -p "去搜索一下美国和伊朗的摩擦的最新情况，然后编写一个脚本，计算从这场摩擦开始到现在经过了多少天，然后找到这个天数的所有质因数分解结果"
```

Stdout: `artifacts/codebuddy_stdout_sample-1.jsonl`

### Sample 2: resumed multi-turn conversation

```shell
codebuddy --output-format stream-json --permission-mode bypassPermissions -p "尝试问我三个问题，然后从我的回答中推断出我的职业。**要求：每次只能问一个问题，一个一个来。**"
codebuddy --output-format stream-json --permission-mode bypassPermissions -r c548bd10-7847-4b6e-b557-31f2db1d8b55 -p "codex、vscode、zotero"
codebuddy --output-format stream-json --permission-mode bypassPermissions -r c548bd10-7847-4b6e-b557-31f2db1d8b55 -p "既有面向学术界的论文，也有面向公众的软件、教程等等，也有给公司内部团队用的产品/报告"
codebuddy --output-format stream-json --permission-mode bypassPermissions -r c548bd10-7847-4b6e-b557-31f2db1d8b55 -p "写代码、写文章、处理数据"
```

Stdout, in order:

- `artifacts/codebuddy_stdout_sample-2.attempt-1.jsonl`
- `artifacts/codebuddy_stdout_sample-2.attempt-2.jsonl`
- `artifacts/codebuddy_stdout_sample-2.attempt-3.jsonl`
- `artifacts/codebuddy_stdout_sample-2.attempt-4.jsonl`

## Required Follow-up Probe Matrix

Before creating an OpenSpec implementation change, run and preserve a versioned probe matrix for the exact CLI version to be supported:

| Area | Probe | Required evidence |
| --- | --- | --- |
| State isolation | Empty service config directory, repeated invocations, and restart | Initial fresh-subprocess evidence captured; service config contains sessions/projects/logs while the service HOME had only planted user settings plus GLib state. |
| Workspace | Controlled `run_dir` containing one skill and `CODEBUDDY.md` | The intended skill and instructions are discovered; no host project configuration is loaded. |
| Resume | Start, exit, then resume in a fresh subprocess | Confirmed with a service-owned config directory; the original `session_id` resumes and repeated `system.init` is accepted. |
| Credentials | SDK-derived token, API key, helper, missing credential, and invalid credential | The SDK-token, missing-token, and invalid-token controls are captured; API-key/helper and Client Credentials still need dedicated credentials. |
| Output schema | `--json-schema` with `json` and `stream-json` output | Exact structured field location, validation failures, and terminal rows are captured. |
| Process events | Reasoning, tool use, tool result, permission denial, and cancellation | Stable mappings and raw references for each event type. |
| Failure | Non-zero exit, timeout, malformed row, and no terminal row | Adapter outcome and audit behavior remain deterministic. |
| Concurrency | Two independent sessions sharing one config directory | Two-session separation is confirmed; sustained contention and cleanup remain open. |

## Future Test Fixtures

The future engine change should turn the existing captures into parser golden fixtures covering:

- valid `init`, `assistant`, `user`, and `result` rows;
- `thinking`, `tool_use`, and `tool_result` mappings;
- `result.is_error` and missing-terminal-row failure handling;
- repeated `system.init` during `-r` resume;
- recovery of the two historical malformed captures, marked as
  provenance-unverified rather than native CLI golden output;
- preservation of raw audit references, extracted session handle, final text, and process events.

## Open Questions

The following remain unverified and must be answered by the probe matrix rather than assumptions:

- actual expiry, revocation, and reauthorization behavior after an interactive
  JWT reaches its deadline;
- public and iOA interactive acquisition eligibility, plus whether either route
  persists an equivalent token in a temporary state or OS keyring;
- whether `--json-schema` emits `structured_output` in `stream-json` terminal rows;
- whether all supported operating systems keep keyring access isolated when `CODEBUDDY_CONFIG_DIR` is set;
- sustained contention and cleanup behavior of concurrent sessions sharing a service-owned configuration directory;
- the remaining generated settings payload required for production policy beyond
  the confirmed `disableAllHooks` and project-source boundary.
- whether a future CLI version or a distinct transport can reproduce physical
  newlines inside a JSON string under native-pipe capture.

## Implementation Handoff for the Next Session

### Current repository boundary

- There is no `server/engines/codebuddy/` package and no CodeBuddy runtime,
  public API, schema, or OpenSpec change yet. The existing engine families are
  the implementation patterns to inspect; do not assume that a CodeBuddy
  parser, adapter profile, model registry, or auth runtime handler already
  exists.
- `artifacts/scripts/probe_codebuddy.py` is an untracked, one-off forensic
  harness. It is not a runtime dependency. The installed
  `codebuddy-agent-sdk==0.3.205` lives only in the shared `$HOME/.ar`
  environment and was not added to this repository's dependency manifest or
  lockfile.
- The next implementation must begin with an OpenSpec change because it adds a
  runtime engine. Follow the runtime SSOT order in `AGENTS.md`: contracts /
  invariants first, then docs/specs, implementation, and tests.

### Decisions already settled

1. Adapter process contract: a new subprocess per attempt, `cwd=run_dir`,
   `-p --output-format stream-json --permission-mode bypassPermissions`, and
   `-r <session-id>` for an exact resume. Never use `--continue`, worktree,
   sandbox, serve, or ACP modes.
2. Workspace contract: materialize `CODEBUDDY.md` and
   `.codebuddy/skills/<skill-id>/SKILL.md` in the run directory. Use a stable,
   service-owned config directory across attempts. Generate controlled settings
   and pass `--settings` with `--setting-sources project`.
3. Settings isolation: `project` source loaded a project sentinel and excluded
   deliberately planted user settings. The service config, not service HOME,
   held CodeBuddy sessions/projects/logs/plugins/traces. Treat plugin-marketplace
   population as normal state growth and budget/clean it deliberately.
4. Stream contract: current native-pipe CLI output is ordinary JSONL. Retain
   stateful malformed-stream recovery for audit continuity, but do not encode
   the historical copied samples as proof of a current CodeBuddy JSONL defect.
5. Terminal outcome: a CodeBuddy auth failure can have `result.is_error=true`
   and subprocess exit code `0`. Completion logic must require a valid terminal
   `result` and inspect its error state, not the exit code alone.

### Authentication decision required before designing the engine

The first implementation plan must select exactly one primary credential
contract; these paths are not interchangeable:

| Primary contract | What the engine receives | What still has to be built or supplied |
| --- | --- | --- |
| Request-scoped explicit token | Caller supplies `CODEBUDDY_AUTH_TOKEN` in `runtime_options.env` | Simplest initial boundary. Set `no_cache=true` when it affects output; token expires/revokes through normal run failure and a new caller-supplied token. |
| Managed interactive login | SDK login URL yields a user JWT | Requires a new durable, redacted engine-secret design and reauthorization UX. The existing SDK writes a token into its temporary auth state, so cleanup is mandatory. Do not reuse host login at runtime. |
| OAuth Client Credentials | Service stores dedicated `client_id/client_secret` and obtains access tokens | Requires dedicated test credentials to prove the official token endpoint and refresh/error behavior. A user JWT cannot stand in for this test. `apiKeyHelper` remains unverified. |

`runtime_options.env` is suitable for the first row: it permits
`CODEBUDDY_AUTH_TOKEN` (only base-process variables such as `HOME`/`PATH` are
protected), stores raw values in `data/run_secrets/<request-id>.env.json`, and
injects them only into the attempt subprocess. It is **request-scoped**, not a
durable service credential store; cleanup deletes those files. Do not mistake
it for the persistent store required by managed interactive login or Client
Credentials.

The recommended planning default, until dedicated OAuth application credentials
are supplied, is the first row: explicit request-scoped `AUTH_TOKEN` only. It
is the only production boundary fully supported by existing storage and
evidence. The SDK login is an onboarding/probe capability, not an adapter
runtime dependency.

### Fixture and worktree handoff

- Raw probe evidence is ignored under `data/codebuddy_probes/`; use it to
  regenerate small, reviewed parser fixtures rather than committing raw tokens,
  host state, or broad trace trees.
- At handoff this worktree also has uncommitted modifications to
  `artifacts/codebuddy_stdout_sample-1.jsonl` and
  `artifacts/codebuddy_stdout_sample-2.attempt-4.jsonl` that normalize historical
  physical newlines into escaped `\n`. They are outside the forensic harness
  outputs and were not reverted. Resolve their intended provenance before using
  them as parser fixtures or relying on a whole-worktree `git diff --check`.

## Next Step

Choose the primary credential contract above, then create an OpenSpec change.
That change should define the engine adapter, runtime model discovery,
materialization policy, parser contract, terminal-error mapping, and direct-pipe
golden tests before implementation begins. Client Credentials evidence is a
hard precondition only if that contract is selected; API-key/helper and
public/iOA paths are not blockers for an explicit-token first release.

## Probe Harness

`artifacts/scripts/probe_codebuddy.py` implements the follow-up matrix as a
forensic utility. Its default cases only capture local CLI metadata and replay
the checked-in samples. Agent cases require `--allow-agent-cases` plus a
dedicated probe credential supplied through a probe-only environment variable;
they never use a host login as a substitute unless the operator explicitly
selects `--allow-host-login`; `--use-host-state` additionally permits the host
CodeBuddy configuration state when the OS credential manager alone is
insufficient. Raw evidence is written beneath the ignored
`data/codebuddy_probes/` directory after known credential values are redacted.
Host state is never copied into the probe evidence or directory snapshots. The
script can append a sanitized result table here only when its explicit
`--update-investigation` option is selected.

## Probe Results: 2026-07-10

All raw evidence for this section is ignored local data under
`data/codebuddy_probes/`. No credentials or host configuration files were
copied into the repository.

### Authentication and state boundary

1. `host-login-baseline` used a temporary `HOME` and
   `CODEBUDDY_CONFIG_DIR`, while allowing operating-system credential-manager
   access. It emitted `apiKeySource=www.codebuddy.ai` and `model=default-model`,
   but ended with `result.subtype=error_during_execution` and an authentication
   prompt. The credential manager alone is insufficient for this host login.
2. `host-state-baseline` additionally used the host CodeBuddy configuration
   state. It succeeded with `apiKeySource=copilot.tencent.com`, `model=hy3`,
   and a `result.success` terminal row. Host-login reuse therefore depends on
   more than an isolated configuration directory and cannot satisfy the
   first-release isolation boundary.
3. With host state available, an intentionally invalid `CODEBUDDY_API_KEY`
   yielded `result.is_error=true` and a 401 error although the process exit
   code was `0`. The returned diagnostic explicitly identified the environment
   variable and advised unsetting it to resume `/login`; an invalid explicit
   API key overrides the usable host login.
4. `sdk-auth-token` used the official Python SDK version `0.3.205` to read the
   existing host login in a whitelisted process environment. The SDK returned a
   resolved result with a token and no login URL. The token was not written to
   evidence: a post-run exact-value scan across the evidence root found zero
   matches.
5. In the same run, an isolated CLI process with no token returned the expected
   `/login` authentication error. With the in-memory SDK token injected as
   `CODEBUDDY_AUTH_TOKEN`, the equivalent fully isolated process returned
   `result.success` (`apiKeySource=copilot.tencent.com`, model `glm-5.2`). A
   deliberately invalid `CODEBUDDY_AUTH_TOKEN` over a working host login
   yielded `result.is_error=true`, 401, and exit code `0`; this is direct
   precedence evidence for `AUTH_TOKEN` over host state.
6. `sdk-interactive-auth` established a new-state China-edition login with
   `environment=internal`. Its final run received an explicit successful auth
   callback and a token, while the equivalent fresh CLI process without a token
   returned `result.is_error=true` and the token-injected process returned
   `result.success`. The SDK temporary state had one token occurrence before
   cleanup; the post-login CLI temporary state and ignored evidence tree had
   zero. This is proof of both the interactive acquisition route and the need
   for explicit temporary-state cleanup.

### Workspace, output, and session observations

- The materialization case succeeded and returned both unique sentinels from
  `CODEBUDDY.md` and `.codebuddy/skills/sr-probe/SKILL.md`; its init event cwd
  was the dedicated probe run directory.
- `--output-format stream-json --json-schema` emitted the expected stream
  envelope and a terminal `result.structured_output` object.
- Contrary to the documented single-result description, `--output-format json`
  emitted a JSON **array** of seven event objects. Its final `result` still
  carried `structured_output`; the probe harness now recognizes this separate
  `json_array` envelope.
- A start and a fresh-process `-r` resume both emitted one `system.init` row,
  shared session ID `probe-e7d87a852a98e5d4603b9446`, and returned their
  expected distinct completion text.
- `service-config-isolation` acquired its token only in the SDK bootstrap, then
  ran every CLI subprocess with a new service HOME and shared service
  `CODEBUDDY_CONFIG_DIR`. A controlled project settings sentinel was observed;
  deliberately planted user-settings sentinels in both expected user locations
  were absent. Start and fresh-process resume shared the requested session ID,
  while two concurrent sessions retained separate IDs. The service config and
  evidence root contained no token occurrences. The service HOME contained
  only the planted `.codebuddy/settings.json` plus GLib state; CodeBuddy
  sessions, projects, logs, plugins, and traces were under the service config.
  Evidence: `data/codebuddy_probes/20260710T115226Z/`.

### Process and failure observations

- Under `bypassPermissions`, CodeBuddy emitted an `assistant.tool_use` block
  with `name=Bash`, wrote and read `.probe-tool-output.txt` inside the probe
  run directory, then produced `result.success`.
- The cancellation harness sent SIGTERM after ten seconds. CodeBuddy exited
  with code `0`, produced no terminal `result`, and retained only init and
  file-history rows. Future adapter completion requires both a valid terminal
  row and subprocess outcome; exit code alone is insufficient.
- Two concurrent host-state sessions with distinct explicit `--session-id`
  values each completed successfully and retained separate session IDs. This
  is positive but limited evidence: it does not prove collision-free cleanup
  under sustained concurrency.
- Native-pipe replay of the exact documented Sample 1 and Sample 2 commands
  found no JSON-string physical newlines in five successful stdout captures.
  The historical malformed files remain useful recovery inputs, but are no
  longer evidence that the currently supported CLI violates JSONL framing.

### Remaining probes

Both the host-login-derived and clean-state China-edition interactive SDK paths
are now verified. They remain user credential acquisition workflows, not a
production service credential design. Valid `CODEBUDDY_API_KEY`, controlled
`apiKeyHelper`, actual token expiry/revocation, public/iOA eligibility, and
OAuth Client Credentials (`client_id`/`client_secret` to `access_token`, then
isolated CLI) still require dedicated service test credentials. Service-config
isolation, project-source settings exclusion, fresh-subprocess resume, and
two-session separation are now established, but full server restart and
sustained contention remain untested. Host-state observations must not be
treated as equivalent to the planned service-owned configuration design.
