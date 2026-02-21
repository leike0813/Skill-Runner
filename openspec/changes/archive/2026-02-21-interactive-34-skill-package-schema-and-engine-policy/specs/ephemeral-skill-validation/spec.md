## MODIFIED Requirements

### Requirement: Temporary skill metadata must satisfy execution constraints
The system MUST validate temporary skill engine declarations with the same contract as persistent installs:
- `engines` MAY be omitted;
- `unsupported_engines` MAY be declared to explicitly deny engines;
- when both are present, they MUST NOT overlap;
- `effective_engines = (engines if provided else all system-supported engines) - unsupported_engines`;
- `effective_engines` MUST be non-empty;
- `artifacts` contract requirements remain unchanged.

#### Scenario: Temporary skill omits engines with valid artifacts
- **WHEN** temporary `runner.json` omits `engines` and declares valid `artifacts`
- **THEN** the system computes `effective_engines` from all system-supported engines minus `unsupported_engines`
- **AND** the temporary package passes metadata validation when result is non-empty

#### Scenario: Temporary skill declares overlapping allow/deny engines
- **WHEN** temporary `runner.json` contains the same engine in both `engines` and `unsupported_engines`
- **THEN** the system rejects the upload request as invalid

#### Scenario: Temporary skill yields empty effective engines
- **WHEN** temporary `runner.json` engine declarations produce an empty `effective_engines`
- **THEN** the system rejects the upload request as invalid
