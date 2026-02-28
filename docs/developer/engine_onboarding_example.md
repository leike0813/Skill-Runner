# Engine Onboarding Example

This document shows the minimal onboarding path for a new engine `demo`.

## 1. Directory Layout

```text
server/engines/demo/
  adapter/
    adapter_profile.json
    execution_adapter.py
    config_composer.py
    command_builder.py
    stream_parser.py
  auth/
    __init__.py
    runtime_handler.py
    protocol/
    callbacks/
    drivers/
```

## 2. Auth Onboarding (Phase2 model)

Implement `server/engines/demo/auth/runtime_handler.py` with:

1. `plan_start`
2. `start_session_locked`
3. `refresh_session_locked`
4. `handle_input`
5. `complete_callback`
6. `cleanup_start_error`
7. `on_session_finalizing`
8. `terminate_session`
9. `requires_parent_trust_bootstrap`

Then wire:

1. Register auth matrix entries (`transport/auth_method/provider_id`).
2. Add handler to manager `_engine_auth_handlers`.

Important:

1. Do not put demo-specific logic into `server/runtime/auth/**`.
2. Keep callback/listener/provider specifics under `server/engines/demo/auth/**`.
3. If protocol code is shared across multiple engines, place it in `server/engines/common/**`.

## 3. Adapter Onboarding

Implement adapter components under `server/engines/demo/adapter/*`:
1. `config_composer.py`
2. `command_builder.py`
3. `stream_parser.py`
4. `execution_adapter.py`
5. `adapter_profile.json`（prompt/session/workspace 三段配置）

Then register the execution adapter class in `server/services/engine_adapter_registry.py`.

## 4. Test Checklist

1. `test_engine_auth_driver_matrix_registration.py`:
   - demo combinations resolve as expected.
2. `test_engine_auth_flow_manager.py`:
   - start/status/input/callback/cancel round-trip.
3. `test_runtime_auth_no_engine_coupling.py`:
   - runtime guard still passes.
4. engine adapter tests:
   - command build
   - parser output
   - session handle restore
