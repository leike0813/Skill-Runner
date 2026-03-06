## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks for run timeline enhancement.
- [x] 1.2 Add delta specs for management UI and interactive job API.

## 2. Backend Timeline Aggregation

- [x] 2.1 Add run-scope timeline aggregation in run observability service.
- [x] 2.2 Implement stable sorting with `event.ts` primary key and deterministic fallback.
- [x] 2.3 Add management API endpoint `/v1/management/runs/{request_id}/timeline/history`.

## 3. Management UI Integration

- [x] 3.1 Add default-collapsed Run Timeline panel at the bottom of Run Detail.
- [x] 3.2 Render five fixed lanes and summary bubbles with expandable details.
- [x] 3.3 Add cursor-based incremental refresh and load-earlier action.

## 4. i18n and Tests

- [x] 4.1 Add i18n keys for timeline panel labels/states.
- [x] 4.2 Add route tests for timeline history endpoint.
- [x] 4.3 Add run observability timeline aggregation tests.
- [x] 4.4 Update UI template and management page tests for timeline panel.
