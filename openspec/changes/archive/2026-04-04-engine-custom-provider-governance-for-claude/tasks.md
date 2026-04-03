## 1. Change Artifacts

- [x] 1.1 Create proposal, design, and delta specs for Claude custom-provider governance

## 2. Generic custom-provider layer

- [x] 2.1 Add engine-scoped custom-provider registry/service with Claude as the first implementation
- [x] 2.2 Add management API models and CRUD routes for `/management/engines/{engine}/custom-providers`

## 3. Claude bootstrap and runtime config

- [x] 3.1 Move Claude bootstrap target to `.claude.json` and initialize `hasCompletedOnboarding=true`
- [x] 3.2 Update Claude runtime config injection so model selection is driven by `settings.json.env`
- [x] 3.3 Stop passing Claude model selection via CLI `--model`

## 4. Catalog, UI, E2E, and harness

- [x] 4.1 Merge Claude official models with configured custom-provider models and expose `source`
- [x] 4.2 Add Claude custom-provider CRUD UI to `/ui/engines`
- [x] 4.3 Update E2E run form to consume merged Claude model catalog
- [x] 4.4 Add `--custom-model` to `agent_harness` for Claude only

## 5. Waiting-auth provider-config flow

- [x] 5.1 Extend auth strategy contracts with `provider_config/custom_provider`
- [x] 5.2 Add Claude provider-config session handling and waiting_auth integration

## 6. Validation

- [x] 6.1 Add targeted tests for custom-provider store, Claude bootstrap, merged catalog, management routes, waiting_auth flow, E2E, and harness
- [x] 6.2 Run targeted pytest
- [x] 6.3 Run targeted mypy
