## 1. Spec And Runtime Alignment

- [x] 1.1 Add OpenSpec proposal, design, and delta specs for low-confidence auth misattribution handling
- [x] 1.2 Tighten adapter and lifecycle auth-failure attribution so only high-confidence auth signals can produce `AUTH_REQUIRED`

## 2. Regression Coverage

- [x] 2.1 Add adapter failfast coverage for low-vs-high confidence auth attribution
- [x] 2.2 Add lifecycle/orchestrator regression tests proving low-confidence auth hints stay diagnostic-only
