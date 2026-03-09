## 1. Single-Source Auth Detection

- [x] 1.1 Keep auth evidence in adapter profiles and common fallback file only.
- [x] 1.2 Remove rule `classify` dependency from adapter profile schema and runtime matcher.
- [x] 1.3 Normalize confidence to `high|low` (engine-specific=high, fallback=low).

## 2. Runtime/Lifecycle Hard Cut

- [x] 2.1 Persist final `auth_signal_snapshot` in execution results.
- [x] 2.2 Make lifecycle consume `auth_signal_snapshot` for auth classification.
- [x] 2.3 Keep `low` auth signal diagnostic-only (no waiting_auth transition).

## 3. Structured RASP Diagnostics

- [x] 3.1 Emit `AUTH_SIGNAL_MATCHED_HIGH/LOW` in `diagnostic.warning`.
- [x] 3.2 Add structured `data.auth_signal` payload in RASP diagnostics.
- [x] 3.3 Update runtime contract schema for `diagnostic.warning.data.auth_signal`.

## 4. SSOT and Guards

- [x] 4.1 Update `auth-detection-layer` spec to parser-signal single-source semantics.
- [x] 4.2 Add/extend invariant rules for single-source and snapshot-only consumption.
- [x] 4.3 Add guard tests for:
  - no legacy YAML rule source consumption
  - no rule-based second-pass detect in runtime chain
  - no hardcoded auth evidence markers in parser/core
