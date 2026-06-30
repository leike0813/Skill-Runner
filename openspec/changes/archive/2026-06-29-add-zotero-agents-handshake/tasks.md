## 1. OpenSpec and docs

- [x] 1.1 Add change proposal, design, tasks, and delta specs for handshake/version management.
- [x] 1.2 Update API reference with handshake request/response and ping boundary.
- [x] 1.3 Update Zotero plugin integration contract with handshake and version workflow.

## 2. Backend implementation

- [x] 2.1 Add backend version helper and set project version to `0.7.2`.
- [x] 2.2 Add handshake request/response models.
- [x] 2.3 Add `POST /v1/system/handshake` without changing `/v1/system/ping`.
- [x] 2.4 Use the version helper for FastAPI metadata and handshake response.

## 3. Version tooling and CI

- [x] 3.1 Add `scripts/bump_version.py` for SemVer bump and tag consistency checks.
- [x] 3.2 Add tag/version consistency check to the release workflow.

## 4. Tests

- [x] 4.1 Cover handshake job, sequence, unknown protocol, and auth policy behavior.
- [x] 4.2 Cover ping semantics remain unchanged.
- [x] 4.3 Cover backend version helper and FastAPI metadata.
- [x] 4.4 Cover bump script update, tag check, mismatch, and invalid SemVer.
