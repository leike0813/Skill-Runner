## 1. OpenSpec Artifacts

- [x] 1.1 Finalize proposal/design/tasks for single-image dual-entrypoint deployment.
- [x] 1.2 Add delta specs for `local-deploy-bootstrap` and `builtin-e2e-example-client`.

## 2. Image Packaging

- [x] 2.1 Update Dockerfile to include `e2e_client` in image build context.
- [x] 2.2 Add or adjust E2E client container entrypoint command.
- [x] 2.3 Keep backend entrypoint as default and verify both entry modes run from same image.

## 3. Docker Compose Layout

- [x] 3.1 Keep `api` as default enabled service.
- [x] 3.2 Add optional `e2e_client` service block using the same image but different startup command.
- [x] 3.3 Comment out `e2e_client` block by default and add inline enable guidance.

## 4. Documentation and Validation

- [x] 4.1 Update `docs/containerization.md` to match new single-image + optional-client compose layout.
- [x] 4.2 Verify `docker compose up` default behavior starts only backend service.
- [x] 4.3 Verify enabling `e2e_client` block starts client service with expected port and backend connectivity.
