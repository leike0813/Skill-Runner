# ui-design-system Specification

## Purpose
TBD - created by archiving change ui-visual-refresh. Update Purpose after archive.
## Requirements
### Requirement: Design token CSS custom properties
The system SHALL define a set of CSS custom properties on `:root` covering color palette, typography, spacing scale, border radii, box shadows, and transition durations. Both the Admin Management UI and E2E Example Client SHALL reference these tokens exclusively — no hardcoded color values or magic numbers in templates.

#### Scenario: Token availability
- **WHEN** any page from the Admin UI or E2E Client is loaded in a browser
- **THEN** the design-system CSS file is loaded and all `--color-*`, `--space-*`, `--font-*`, `--radius-*`, `--shadow-*`, `--transition-*` custom properties are available on `:root`

#### Scenario: Dark sidebar navigation
- **WHEN** the Admin UI or E2E Client renders a page with navigation
- **THEN** the sidebar/header navigation area SHALL use the dark palette tokens (`--color-nav-bg`, `--color-nav-text`) and the content area SHALL use the light palette tokens

### Requirement: Shared CSS file served as static asset
The system SHALL serve a single CSS file at a static path accessible by both the Admin UI and the E2E Client. Both applications' base templates SHALL include a `<link>` element referencing this file.

#### Scenario: CSS file loading
- **WHEN** a browser loads any Admin UI page at `/ui/*`
- **THEN** the response HTML SHALL contain a `<link rel="stylesheet">` pointing to the shared design-system CSS file

#### Scenario: E2E Client CSS loading
- **WHEN** a browser loads any E2E Client page
- **THEN** the response HTML SHALL contain a `<link rel="stylesheet">` pointing to the shared design-system CSS file

### Requirement: Typography foundation
The system SHALL use 'Inter' as the primary font family with a system font stack fallback (`system-ui, -apple-system, sans-serif`). The CSS file SHALL import Inter via Google Fonts. If the font fails to load, layout SHALL remain intact using the fallback stack.

#### Scenario: Font loading success
- **WHEN** the browser has network access to Google Fonts
- **THEN** all UI text SHALL render in Inter

#### Scenario: Font loading failure
- **WHEN** the browser cannot reach Google Fonts (offline or air-gapped deployment)
- **THEN** all UI text SHALL render using the system font stack with no layout breakage

### Requirement: Micro-animation tokens
The system SHALL define CSS transition tokens for interactive elements. Buttons, links, table rows, cards, and expandable sections SHALL have hover/focus transitions using `--transition-fast` (≤150ms) and `--transition-normal` (≤300ms).

#### Scenario: Button hover
- **WHEN** a user hovers over a primary action button
- **THEN** the button SHALL display a smooth color/shadow transition within `--transition-fast` duration

#### Scenario: Table row hover
- **WHEN** a user hovers over a data table row
- **THEN** the row SHALL display a subtle background highlight transition

### Requirement: Consistent layout utilities
The system SHALL provide CSS utility classes for cards, tables, status badges, and page layout containers. All Admin UI and E2E Client pages SHALL use these utilities for consistent spacing and visual hierarchy.

#### Scenario: Card component
- **WHEN** a page displays a grouped content block (e.g., skill detail, engine status)
- **THEN** the block SHALL be wrapped in a card with consistent padding, border-radius, and shadow from design tokens

#### Scenario: Status badges
- **WHEN** a run status, engine status, or auth status is displayed
- **THEN** it SHALL use a color-coded badge component with colors derived from design tokens (success/warning/error/info)

