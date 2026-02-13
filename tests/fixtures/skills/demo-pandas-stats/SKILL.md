---
name: demo-pandas-stats
description: Calculate statistics using pandas with a pre-written script.
---

# Pandas Data Stats

You are a data analysis agent.
Your task is to execute a provided Python script to analyze a CSV file.

## Inputs
- `{{ input.csv_file }}`: Path to the CSV file.
- `{{ parameter.column }}`: The column to analyze.
- `{{ skill_dir }}`: The directory where this skill is installed.

## Instructions

1.  **Locate the Script**:
    The script is located at `{{ skill_dir }}/scripts/analyze.py`.

2.  **Execute the Script**:
    Run the script using `python3` with the CSV file and Column name as arguments:
    ```bash
    python3 {{ skill_dir }}/scripts/analyze.py "{{ input.csv_file }}" "{{ parameter.column }}"
    ```

3.  **Output**:
    - Capture the JSON output from stdout.
    - Return it as the final result.

## Important
- The environment has `pandas` installed.
- Do NOT write any new python code. Use the provided script.
