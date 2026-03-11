## ADDED Requirements

### Requirement: E2E run form MUST submit file input values as declarative uploads-relative paths
The built-in E2E client MUST include file-sourced input values in `POST /v1/jobs` payload `input`, where each value is an `uploads/`-relative path.

#### Scenario: installed run submits mixed inline and file input values
- **WHEN** user submits a run form with both inline and file fields
- **THEN** the create-run payload includes inline values and file path values together in `input`
- **AND** each file value points to the uploaded zip entry path relative to `uploads/`

### Requirement: E2E file upload zip MUST preserve original filenames under field folders
The built-in E2E client MUST package uploaded files under `<field>/<original_filename>` entries instead of renaming them to schema keys.

#### Scenario: uploaded file keeps original filename
- **WHEN** user uploads `input.txt` for field `input_file`
- **THEN** upload zip contains `input_file/input.txt`
- **AND** `input.input_file` is set to `input_file/input.txt`
