## 1. Protocol And SSOT

- [x] 1.1 Restore `custom_provider` in runtime schema enums for pending auth, method selection, and auth input acceptance
- [x] 1.2 Update shared OpenSpec main specs to recognize `provider_config/custom_provider`
- [x] 1.3 Update API documentation to describe `custom_provider` as a formal provider-config auth semantic

## 2. Runtime And Tests

- [x] 2.1 Ensure Claude custom provider waiting_auth continues to emit schema-valid `custom_provider` payloads
- [x] 2.2 Add schema regression tests for `pending_auth`, `pending_auth_method_selection`, and `auth.input.accepted`
- [x] 2.3 Add runtime/auth replay regression coverage for `custom_provider` waiting_auth

## 3. Verification

- [x] 3.1 Run targeted protocol/orchestration tests
- [x] 3.2 Run runtime mandatory regression suite
- [x] 3.3 Validate the new OpenSpec change artifacts
