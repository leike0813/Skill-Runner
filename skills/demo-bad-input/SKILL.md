---
name: demo-bad-input
description: A skill that requires a missing input file to trigger validation failure.
---

# Demo: Bad Input

This skill requires an input file.

## Inputs
- `{{ input.input_file }}`: Required input file.

## Instructions
1. Attempt to read the input file.
2. If the file is missing, stop immediately.

## Result Format
Output any JSON object.
