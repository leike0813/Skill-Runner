## 1. OpenSpec and Docs

- [x] 1.1 Add and validate OpenSpec artifacts for the managed Zotero Bridge plugin.
- [x] 1.2 Document managed CLI PATH registration, global wrapper skill install, profile env behavior, and local/Docker deployment.

## 2. Submodule and Build Inputs

- [x] 2.1 Add `plugins/zotero-bridge-cli-bundle` as a submodule on branch `host-bridge/zotero-bridge-cli-bundle`.
- [x] 2.2 Ensure Docker build context includes `plugins/` so container bootstrap can install the bundle.

## 3. Managed Installer

- [x] 3.1 Add bundle manifest/platform resolution and SHA256 verification.
- [x] 3.2 Install POSIX/Windows CLI files into the managed prefix bin directory.
- [x] 3.3 Sync the wrapper skill into managed global skill directories for Codex, Claude, Gemini, Qwen, and OpenCode.
- [x] 3.4 Install a sanitized managed profile and expose `ZOTERO_BRIDGE_PROFILE` through runtime profile env.

## 4. Tests

- [x] 4.1 Add unit coverage for platform mapping, SHA validation, POSIX/Windows install outputs, profile sanitization, and global skill sync.
- [x] 4.2 Add regression coverage for runtime profile env and submodule/Docker wiring.
- [x] 4.3 Run targeted validation for OpenSpec and changed code.
