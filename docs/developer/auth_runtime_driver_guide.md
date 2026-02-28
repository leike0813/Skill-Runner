# Auth Runtime Driver Guide

## 1. Design Boundary

Auth runtime adopts strict layering:

1. `server/runtime/auth/**` is engine-agnostic orchestration only.
2. `server/engines/<engine>/auth/**` contains all engine-specific auth behavior.
3. `EngineAuthFlowManager` is a facade (lock/store/dispatch), not an engine business host.
4. Cross-engine shared auth protocol code lives in `server/engines/common/**`.

Hard rules:

1. `server/runtime/auth/**` MUST NOT import `server/engines/**`.
2. `server/runtime/auth/**` MUST NOT branch on engine names (`if engine == ...`).
3. New engine auth logic goes to `server/engines/<engine>/auth/runtime_handler.py`.

## 2. Runtime Call Chain

Unified flow:

1. `start_session`:
   - `AuthSessionStartPlanner.plan_start(...)`
   - `AuthSessionStarter.start_from_plan_locked(...)`
2. `get_session`:
   - `AuthSessionRefresher.refresh_session_locked(...)`
3. `input_session`:
   - `AuthSessionInputHandler.handle_input(...)`
   - then refresh and snapshot
4. callback endpoints:
   - `AuthSessionCallbackCompleter.complete_*_callback(...)`
5. `cancel_session`:
   - `handler.terminate_session(...)` (engine-specific)
   - manager terminalization + lock release

## 3. Engine Runtime Handler Contract

Each engine handler should implement:

1. `plan_start(...) -> AuthStartPlan`
2. `start_session_locked(plan, callback_base_url, context) -> _AuthSession`
3. `refresh_session_locked(session) -> bool`
4. `handle_input(session, kind, value) -> None`
5. `complete_callback(channel, session, state, code, error) -> bool`
6. `cleanup_start_error(context) -> None`
7. `on_session_finalizing(session) -> None`
8. `terminate_session(session) -> bool`
9. `requires_parent_trust_bootstrap() -> bool`

`refresh_session_locked` returns `True` when handler consumed the refresh path.

## 4. What Belongs Where

Runtime (`server/runtime/auth/**`) owns:

1. Session orchestration and lifecycle plumbing.
2. Transport-neutral state transitions and terminalization hooks.
3. Session store and auth event logs.
4. Callback state one-shot consumption framework.

Engine handler owns:

1. OAuth/device/API-key protocol details.
2. Listener startup/stop rules.
3. Provider-specific rollback.
4. CLI/PTY process semantics per engine.
5. Credential write semantics per engine.

Shared protocol layer owns:

1. Cross-engine reusable provider protocol utilities.
2. Current location: `server/engines/common/openai_auth/*` for CodeX/OpenCode OpenAI reuse.

## 5. Adding a New Engine Auth Driver

1. Create `server/engines/<engine>/auth/runtime_handler.py`.
2. Implement the contract methods above.
3. Register support matrix in manager driver registry (`transport/auth_method/provider_id`).
4. Add handler instance to manager `_engine_auth_handlers`.
5. Add tests:
   - driver matrix registration
   - start/refresh/input/callback/cancel flow
   - lock release on terminal paths

## 6. Common Failure Points

1. Active session lock not released:
   - verify `on_session_finalizing` + manager finalize path.
2. Callback received but session not closing:
   - verify state resolve/consume and handler `complete_callback`.
3. Start succeeds then instant failure:
   - verify `cleanup_start_error` and trust injection.
4. runtime guard violations:
   - run `tests/unit/test_runtime_auth_no_engine_coupling.py`.
