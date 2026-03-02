## 1. Package Restructure

- [x] 1.1 Create `server/models/` package and migrate domain modules (`common`, `run`, `skill`, `engine`, `interaction`, `management`, `runtime_event`, `error`)
- [x] 1.2 Move public facade exports to `server/models/__init__.py` and keep `__all__` parity
- [x] 1.3 Remove legacy root files `server/models.py` and `server/models_*.py` after migration

## 2. Import and Dependency Migration

- [x] 2.1 Replace internal imports of `server.models_*` with `server.models.*` (or package-relative imports inside the package)
- [x] 2.2 Update all affected test monkeypatch/import paths to new package layout
- [x] 2.3 Run residual scan to ensure no old model-module paths remain in `server/` and `tests/`

## 3. Guards and Documentation

- [x] 3.1 Update `tests/unit/test_models_module_structure.py` to validate package-based boundary (`server/models/`) instead of `server/models.py` file assumptions
- [x] 3.2 Add/adjust structure guard to fail on reintroduced root-level `models_*.py` files
- [x] 3.3 Update `docs/project_structure.md` and related docs to reflect `server/models/` ownership boundary

## 4. Validation and Acceptance

- [x] 4.1 Run targeted pytest for model boundary and affected routes/services
- [x] 4.2 Run runtime mandatory contract suite from `AGENTS.md` to confirm schema/state behavior parity
- [x] 4.3 Run mypy on `server/models/` and core dependents, then confirm OpenSpec change is apply-ready
