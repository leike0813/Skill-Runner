## 1. Shared Credentials

- [x] 1.1 Add repository-tracked shared OAuth credentials files under engine protocol dirs.
- [x] 1.2 Update startup env loading to read both shared credentials files.
- [x] 1.3 Remove `.env.engine_auth.local` startup loading path.
- [x] 1.4 Add scoped secret scanning exemptions for the two credential files.

## 2. Strategy & Service

- [x] 2.1 Extend `engine_auth_strategy` schema with `high_risk_methods`.
- [x] 2.2 Mark `opencode/google` oauth_proxy + cli_delegate methods as high risk.
- [x] 2.3 Expose high-risk capability queries from `EngineAuthStrategyService`.

## 3. UI & In-Conversation Warning

- [x] 3.1 Show high-risk short label on management auth method buttons.
- [x] 3.2 Show high-risk warning in in-conversation method/challenge prompts.
- [x] 3.3 Remove OpenCode method fallback hardcoding in management UI menu path.

## 4. Docs & Validation

- [x] 4.1 Add high-risk notice for opencode+antigravity auth in README.
- [x] 4.2 Run targeted unit tests and type checks for touched modules.
- [x] 4.3 Run `openspec validate --change bundle-oauth-proxy-credentials-and-antigravity-risk-warning`.
