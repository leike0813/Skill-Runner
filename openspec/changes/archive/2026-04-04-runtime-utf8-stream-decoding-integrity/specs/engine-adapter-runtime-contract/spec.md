## MODIFIED Requirements

### Requirement: Runtime stream text views MUST preserve UTF-8 decoding integrity across chunk boundaries

The system MUST preserve the textual meaning of raw runtime bytes when converting `stdout` / `stderr` chunks into log text and live parser input.

#### Scenario: execution stream decoding preserves split multibyte UTF-8 characters

- **WHEN** the runtime reads `stdout` or `stderr` in multiple raw byte chunks
- **AND** a valid UTF-8 multibyte character is split across chunk boundaries
- **THEN** `stdout/stderr.log` MUST decode that character correctly
- **AND** the live parser input text MUST match the same once-decoded UTF-8 replacement text
- **AND** the system MUST NOT inject extra replacement characters solely because of chunk boundaries

#### Scenario: execution stream decoding still replaces genuinely invalid bytes

- **WHEN** the runtime reads raw bytes that are not valid UTF-8
- **THEN** the text view MAY include replacement characters
- **AND** those replacements MUST correspond only to genuinely invalid byte sequences

### Requirement: Strict replay MUST reconstruct the same UTF-8 text truth as live execution

The system MUST decode `io_chunks` for strict replay using the same incremental UTF-8 semantics as the live execution path.

#### Scenario: strict replay preserves split multibyte UTF-8 characters

- **WHEN** strict replay rebuilds text from `io_chunks`
- **AND** a valid UTF-8 multibyte character is split across multiple stored chunks
- **THEN** the replay rows' `text` MUST match the once-decoded UTF-8 replacement text of the original byte stream
- **AND** replay MUST NOT reintroduce chunk-boundary replacement drift

#### Scenario: byte references remain anchored to raw bytes

- **WHEN** the runtime exposes `raw_ref.byte_from` and `raw_ref.byte_to`
- **THEN** those byte ranges MUST remain anchored to the original raw byte stream
- **AND** this change MUST NOT alter the `io_chunks` byte SSOT or its file format
