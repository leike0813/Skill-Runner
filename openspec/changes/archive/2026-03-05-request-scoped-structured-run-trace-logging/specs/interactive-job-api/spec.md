## ADDED Requirements

### Requirement: Upload orchestration MUST expose request-scoped trace milestones

Interactive jobs upload path MUST emit structured trace milestones so operators can identify where a request stopped before run binding or dispatch.

#### Scenario: cache hit upload path is fully traceable
- **WHEN** upload path resolves a cache hit
- **THEN** backend MUST emit `upload.cache.hit`
- **AND** the event MUST include `request_id` and cached `run_id`

#### Scenario: cache miss upload path is fully traceable
- **WHEN** upload path creates and binds a new run
- **THEN** backend MUST emit `upload.run.created` and `upload.request_run.bound`
- **AND** events MUST preserve the same `request_id`

### Requirement: Interaction/auth transitions MUST be traceable with stable event codes

Interactive reply and in-conversation auth handling MUST emit stable structured trace events for accepted/rejected replies and auth progression.

#### Scenario: reply rejected trace
- **WHEN** interaction reply is rejected due to stale or invalid state
- **THEN** backend MUST emit `interaction.reply.rejected`
- **AND** the event MUST include `request_id` and a stable rejection code

#### Scenario: auth completion trace
- **WHEN** auth submission completes and resume ticket is issued
- **THEN** backend MUST emit `auth.completed`
- **AND** the event MUST include `request_id`, `run_id`, and the resume ticket id
