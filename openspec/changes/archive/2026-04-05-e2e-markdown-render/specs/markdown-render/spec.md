# Markdown Rendering Specification

## ADDED Requirements

### Requirement: Chat messages MUST render Markdown syntax

The system SHALL render Markdown syntax in chat messages for both agent and user roles.

#### Scenario: Basic Markdown elements in agent message
- **WHEN** agent sends a message containing headings, lists, bold, and italic text
- **THEN** the chat bubble displays formatted Markdown with proper visual hierarchy

#### Scenario: Basic Markdown elements in user message
- **WHEN** user sends a message containing Markdown syntax
- **THEN** the chat bubble displays formatted Markdown consistently with agent messages

### Requirement: Code blocks MUST render with monospace font

The system SHALL render fenced code blocks with monospace font and distinct background styling.

#### Scenario: Inline code rendering
- **WHEN** message contains inline code wrapped in backticks (e.g., `console.log()`)
- **THEN** the code is displayed in monospace font with light gray background

#### Scenario: Fenced code block rendering
- **WHEN** message contains a fenced code block (triple backticks)
- **THEN** the code block is displayed with padding, distinct background, and monospace font

### Requirement: Tables MUST render with visible borders

The system SHALL render Markdown tables with visible cell borders and header styling.

#### Scenario: Standard Markdown table
- **WHEN** message contains a Markdown table with header row and data rows
- **THEN** the table displays with visible borders, header background, and proper cell alignment

#### Scenario: Table with multiple columns
- **WHEN** message contains a table with 4 or more columns
- **THEN** all columns are visible and readable without horizontal scrolling in the chat bubble

### Requirement: Blockquotes MUST render with visual distinction

The system SHALL render blockquotes with left border and muted text color.

#### Scenario: Single paragraph blockquote
- **WHEN** message contains a blockquote (text prefixed with `>`)
- **THEN** the quote is displayed with a left border and muted text color

### Requirement: Links MUST render as clickable elements

The system SHALL render Markdown links as clickable anchor elements.

#### Scenario: Standard Markdown link
- **WHEN** message contains a link in format `[text](url)`
- **THEN** the link is displayed as a clickable element with blue color

### Requirement: Math formulas MUST render with KaTeX

The system SHALL render LaTeX math formulas using KaTeX when enclosed in dollar sign delimiters.

#### Scenario: Inline math formula
- **WHEN** message contains text with `$E = mc^2$` inline formula
- **THEN** the formula is rendered as properly formatted mathematical notation within the text

#### Scenario: Display math formula
- **WHEN** message contains a block with `$$\sum_{i=1}^n x_i$$` display formula
- **THEN** the formula is rendered as a centered block with proper mathematical notation

### Requirement: Plain/Bubble view switching MUST preserve Markdown formatting

The system SHALL support switching between Plain view and Bubble view for chat display.

#### Scenario: Switch from Plain to Bubble view
- **WHEN** user clicks the "Bubble" view button while in Plain view
- **THEN** all chat messages re-render using bubble-style layout with Markdown formatting preserved

#### Scenario: Switch from Bubble to Plain view
- **WHEN** user clicks the "Plain" view button while in Bubble view
- **THEN** all chat messages re-render using plain list layout with Markdown formatting preserved

### Requirement: Thinking card content MUST render with Markdown support

The system SHALL render thinking card content with Markdown support.

#### Scenario: Thinking card with Markdown content
- **WHEN** thinking process generates text containing Markdown syntax
- **THEN** the thinking card displays formatted Markdown with proper styling

### Requirement: Final summary content MUST render with Markdown support

The system SHALL render final summary content with Markdown support.

#### Scenario: Final summary with Markdown content
- **WHEN** task completion generates a final summary containing Markdown syntax
- **THEN** the final summary card displays formatted Markdown with proper styling

