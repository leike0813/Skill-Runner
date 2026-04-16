## 1. Stage 0 Guardrails

- [x] 1.1 Add change artifacts and the `run-store-modularization` delta spec.
- [x] 1.2 Add or reorganize façade smoke coverage around `RunStore` bootstrap, cache, and interaction roundtrips.

## 2. Stage 1 Database / Bootstrap

- [x] 2.1 Introduce `RunStoreDatabase` and `RunStoreSchemaMigration`.
- [x] 2.2 Refactor `RunStore` bootstrap methods to delegate to the database service without changing public behavior.
- [x] 2.3 Add focused database/migration tests and keep existing run-store regressions green.

## 3. Stage 2 Request / Run / Cache

- [x] 3.1 Introduce `RunRequestStore`, `RunRegistryStore`, and `RunCacheStore`.
- [x] 3.2 Refactor `RunStore` request/run/cache methods to delegate through those stores.
- [x] 3.3 Add focused request/cache tests and begin shrinking `tests/unit/test_run_store.py`.

## 4. Future Stages

- [x] 4.1 Extract projection/state/dispatch/recovery/cancel persistence into dedicated stores.
- [x] 4.2 Extract interactive runtime, interaction, auth, and resume persistence into dedicated stores.
- [x] 4.3 Slim `RunStore` into a lightweight façade and finish splitting `tests/unit/test_run_store.py`.

## 5. Validation

- [x] 5.1 Run targeted `pytest` for the new run-store database/request/cache tests plus `tests/unit/test_run_store.py`.
- [x] 5.2 Run `mypy --follow-imports=skip server/services/orchestration`.
