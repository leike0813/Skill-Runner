## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks and delta specs for ttyd port decoupling.

## 2. Runtime & Deploy Defaults

- [x] 2.1 Update UI shell default ttyd port to `17681` in runtime code.
- [x] 2.2 Update compose files to use `17681:17681` and set `UI_SHELL_TTYD_PORT=17681`.
- [x] 2.3 Add compose inline warning that host/container ttyd ports must remain same-number mapping.

## 3. Local Script & Docs

- [x] 3.1 Update local deploy script default to `UI_SHELL_TTYD_PORT=17681`.
- [x] 3.2 Update README (EN/CN/JA/FR) docker run/compose ttyd port examples to `17681`.

## 4. Tests & Validation

- [x] 4.1 Update UI shell manager unit tests for new default port.
- [x] 4.2 Run targeted tests and confirm no behavior regression.
- [x] 4.3 Run `openspec validate decouple-ui-ttyd-port-from-system-service --type change`.
