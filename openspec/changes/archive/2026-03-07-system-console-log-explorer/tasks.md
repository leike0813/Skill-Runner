## 1. OpenSpec Artifacts

- [x] 1.1 Create change artifacts (proposal/design/tasks + delta specs).

## 2. Backend API

- [x] 2.1 Add system log query models (`ManagementSystemLogItem`, `ManagementSystemLogQueryResponse`).
- [x] 2.2 Implement whitelist-based system/bootstrap log query service with filtering and cursor pagination.
- [x] 2.3 Add `GET /v1/management/system/logs/query` route with parameter validation.

## 3. Management UI

- [x] 3.1 Rename settings semantic copy to System Console (route unchanged).
- [x] 3.2 Add Log Explorer panel with source switch, filters, fixed-height list, and load-more.
- [x] 3.3 Ensure existing logging settings and data reset modules remain functional.

## 4. Documentation

- [x] 4.1 Update `docs/api_reference.md` with new management log query endpoint details.
- [x] 4.2 Update `docs/dev_guide.md` management API list to include new endpoint.

## 5. Tests

- [x] 5.1 Add backend route/service tests for source whitelist, filters, and pagination.
- [x] 5.2 Update UI route tests for System Console copy and Log Explorer controls.
