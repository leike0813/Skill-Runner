## 1. OpenSpec Artifacts

- [x] 1.1 Finalize proposal/design/tasks for compose template release assets.
- [x] 1.2 Add delta specs for `local-deploy-bootstrap` and `builtin-e2e-example-client`.

## 2. Release Compose Template

- [x] 2.1 Add `docker-compose.release.tmpl.yml` that uses image-based startup and keeps optional `e2e_client` commented by default.
- [x] 2.2 Add `scripts/render_release_compose.py` to render template with `image_repo` + `image_tag`.
- [x] 2.3 Add compose validation step (`docker compose config`) for rendered output.

## 3. CI / Release Assets

- [x] 3.1 Update Docker publish workflow to render compose asset only for tag releases (`v*`).
- [x] 3.2 Upload `docker-compose.release.yml` and `docker-compose.release.yml.sha256` to GitHub release assets.
- [x] 3.3 Ensure non-tag workflow runs do not produce compose release assets.

## 4. Documentation

- [x] 4.1 Update `docs/containerization.md` to document local compose vs release compose usage.
- [x] 4.2 Document that release compose should be downloaded from release assets and directly pull fixed tag images.

## 5. Verification

- [x] 5.1 Verify local compose remains build-first and works with `docker compose up --build`.
- [x] 5.2 Verify rendered release compose uses pinned image tags and starts successfully.
