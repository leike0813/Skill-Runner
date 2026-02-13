---
name: demo-prime-number
description: Analyze a markdown file for prime numbers using a dedicated script.
---

# Prime Number Analyzer

You are a precise data analysis assistant.
Task: Read a markdown file, parse numbers, apply a divisor, and identify prime numbers using the provided script.

## Inputs
- `{{ input.input_file }}`: Absolute path to the source markdown file.
- `{{ input.divisor }}`: Divisor scalar (Integer, Default: 1).

## Instructions

1. **Read & Parse (NO HALLUCINATIONS):**
   - The input file is located at `{{ input.input_file }}`.
   - **Action**: Use `read_file` on `{{ input.input_file }}`.
   - **Verification**: If `read_file` returns an error (e.g. file not found), you MUST STOP and report the error. Do NOT invent data.
   - **Process**: Parse the *actual* lines from the file content you read.
   - For each line:
     - Parse the content as a number.
   - For each number found, perform the Division Check:
     - Divide the number by `{{ parameter.divisor }}` (integer division).
     - Keep the result if it is an integer.
     - Discard if non-integer.
       - Check this **Result** (NOT the original number).
       - If the result is NOT an integer (e.g. 3.5) or NOT a number (e.g. "abc"), mark it as Rejected.
       - Record the reason for rejection (e.g., "Not an integer", "Invalid format").

2. **Execute Prime Check:**
   - Write the list of *candidate integers* (just the values) to a temporary file named `candidates.json` in `{{ run_dir }}`.
   - Execute the validation script:
     ```bash
     python3 {{ skill_dir }}/scripts/check_primes.py candidates.json
     ```
   - Capture the JSON output from the script (stdout).

3. **Generate Artifacts:**
   Merge your rejection list with the script's results to generate two files in `{{ run_dir }}`:

   **A. primes.md**
   - List key features: A list of all identified prime numbers, sorted ascending.

   **B. results.json**
   - A list of objects for EVERY original line.
   - Schema:
     ```json
     {
       "original_line": "...",
       "parsed_integer": 10,
       "transformed_value": 5.0,
       "is_prime": true,       // From script
       "factor": null,        // From script (if composite, e.g. 2). Null if prime.
       "reason": "..."        // "Divisible by {factor}" if composite. "Not an integer..." if rejected by LLM.
     }
     ```

4. **Construct Final Output:**
   Output the result JSON pointing to the artifacts.

## Result Format
Output the final result strictly as a valid JSON object in a ```json code block:
{
  "primes_file_path": "{{ run_dir }}/primes.md",
  "results_file_path": "{{ run_dir }}/results.json"
}
