## MODIFIED Requirements

### Requirement: Enforce engine declaration
The system MUST validate engine compatibility declarations in `assets/runner.json` using combined allow/deny semantics:
- `engines` MAY be omitted;
- `unsupport_engine` MAY be declared to explicitly deny engines;
- when both are present, they MUST NOT overlap;
- `effective_engines = (engines if provided else all system-supported engines) - unsupport_engine`;
- `effective_engines` MUST be non-empty.

#### Scenario: Engines omitted and deny-list omitted
- **WHEN** `assets/runner.json` omits both `engines` and `unsupport_engine`
- **THEN** the system treats the skill as allowing all system-supported engines
- **AND** the package passes engine contract validation

#### Scenario: Explicit allow-list with deny-list
- **WHEN** `assets/runner.json` declares non-empty `engines` and optional `unsupport_engine` without overlap
- **THEN** the system computes `effective_engines` from allow-list minus deny-list
- **AND** the package passes engine contract validation when `effective_engines` is non-empty

#### Scenario: Allow-list overlaps deny-list
- **WHEN** `assets/runner.json` declares `engines` and `unsupport_engine` with duplicated engine entries
- **THEN** the system rejects the package as invalid

#### Scenario: Effective engines becomes empty
- **WHEN** the computed `effective_engines` is empty after applying `unsupport_engine`
- **THEN** the system rejects the package as invalid
