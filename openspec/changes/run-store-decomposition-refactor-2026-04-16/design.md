# Design

## Overview

The refactor keeps `RunStore` as the stable façade and moves implementation into internal sub-stores, sharing one `RunStoreDatabase` bootstrap/connection layer.

## Staged decomposition

1. Guardrails
   Freeze public `RunStore` behavior and begin splitting `test_run_store.py`.
2. Database/bootstrap
   Move sqlite connection, initialization, and interactive-runtime migration into `RunStoreDatabase`.
3. Request/run registry and cache
   Move request CRUD, run registry, and cache persistence into dedicated stores while keeping façade delegation.
4. Projection/state/recovery
   Move projection, run/dispatch state, recovery metadata, cancel flags, and cleanup scans into dedicated stores.
5. Interactive/auth/resume
   Move interactive runtime, pending interaction/auth, resume tickets, interaction history, and reply flows into dedicated stores.
6. Façade slimming
   Reduce `RunStore` to shared wiring and backward-compatible delegation.

## Compatibility constraints

- No schema redesign in this change.
- No caller migration away from `RunStore` in this change.
- New typed records stay internal and must not change existing dict/JSON outputs.
