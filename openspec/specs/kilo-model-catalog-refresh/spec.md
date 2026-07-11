# kilo-model-catalog-refresh

## Purpose

TBD

## Requirements

### Requirement: Kilo model probing MUST require confirmed installation

Startup, full-registry, API, UI, and post-upgrade refresh paths MUST execute the Kilo model command only when the latest engine status has `present=true` and no probe error. Absent or unknown status MUST skip without warning or a background task.

#### Scenario: Kilo is not installed at startup
- **WHEN** model catalog lifecycle starts
- **THEN** no Kilo catalog task or Kilo subprocess is created and the existing seed or cache snapshot remains readable


### Requirement: Managed Kilo installation MUST trigger one catalog refresh

After a successful Kilo install or upgrade, engine management MUST refresh installation status first and schedule exactly one model catalog refresh only if installation is confirmed.

#### Scenario: Kilo installation succeeds
- **WHEN** the status refresh confirms the installed binary
- **THEN** one Kilo model refresh is scheduled after the status update

