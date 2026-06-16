# runtime-network-diagnostics Specification

## Purpose
TBD - created by archiving change add-runtime-network-client-address-api. Update Purpose after archive.
## Requirements
### Requirement: Backend MUST expose observed client address

The system SHALL expose a versioned diagnostic endpoint that returns the client IP address observed by the backend for the current HTTP request.

#### Scenario: client address is available

- **WHEN** a client calls `GET /v1/runtime/network/client-address`
- **AND** the ASGI request contains a client host
- **THEN** the response status is `200`
- **AND** the response body includes `client_ip` equal to that backend-observed host

#### Scenario: forwarding headers are not interpreted by the endpoint

- **WHEN** a client calls `GET /v1/runtime/network/client-address` with forwarding headers
- **THEN** the endpoint uses the backend-observed request peer address
- **AND** it does not derive `client_ip` from untrusted forwarding headers

