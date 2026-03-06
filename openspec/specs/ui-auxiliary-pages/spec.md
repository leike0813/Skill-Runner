# ui-auxiliary-pages Specification

## Purpose
TBD - created by archiving change ui-visual-refresh. Update Purpose after archive.
## Requirements
### Requirement: Styled OAuth callback success page
The OAuth callback handler SHALL return a styled HTML page upon successful authentication. The page SHALL display a success icon, engine name, and a confirmation message. The page SHALL use inline `<style>` referencing the same visual design language (colors, typography, spacing) as the main UI.

#### Scenario: OAuth callback success
- **WHEN** an OAuth callback is received and processed successfully
- **THEN** the browser SHALL display a styled page with a success indicator, the engine name, and a message such as "Authentication successful — you may close this tab"
- **AND** the page SHALL NOT display raw JSON or unstyled text

### Requirement: Styled OAuth callback error page
The OAuth callback handler SHALL return a styled HTML page when authentication fails. The page SHALL display an error icon, error description, and a suggestion to retry. The page SHALL use the same inline visual design language.

#### Scenario: OAuth callback error
- **WHEN** an OAuth callback is received but processing fails (invalid state, expired token, etc.)
- **THEN** the browser SHALL display a styled error page with an error indicator, the error description, and a retry suggestion
- **AND** the page SHALL NOT display a raw JSON error body or Python traceback

### Requirement: Styled browser-facing error page
When a route returns an error to a browser-based client (non-API), the system SHALL render a minimal, styled error page instead of raw JSON. This applies to the E2E Client proxy layer and the Admin UI error handler.

#### Scenario: Backend unreachable — browser client
- **WHEN** the E2E Client or Admin UI encounters a backend connection error for a browser request (Accept: text/html)
- **THEN** the response SHALL be a styled HTML page showing the error title (e.g., "Service Unavailable") and a brief message
- **AND** the page SHALL NOT display a raw JSON `{"detail": ...}` body

#### Scenario: Backend unreachable — API client
- **WHEN** an API client (Accept: application/json) encounters the same error
- **THEN** the response SHALL remain a JSON error object (existing behavior unchanged)

#### Scenario: 404 page
- **WHEN** a browser navigates to a non-existent UI route
- **THEN** the response SHALL be a styled HTML page with a 404 message and a link back to the home page

