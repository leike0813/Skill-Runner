---
name: demo-bible-verse
description: Randomly selects a Bible verse, translates it, and saves it to text.md and info.json.
---

# Demo: Bible Verse Generator

You are a helpful assistant.
Task: Randomly select a Bible verse and process it according to the parameters.

## Inputs
- `{{ parameter.language }}`: Target language for the verse.

## Instructions
1. Randomly select a verse from the Bible.
2. Translate the verse content to `{{ parameter.language }}`. Keep the citation (Book Chapter:Verse) clear.
3. Write the translated verse and citation to a file named "text.md" in the current directory (`{{ run_dir }}`).
   - You MUST use a tool (like run_shell_command with 'echo' or 'printf') to write this file.
   - Format: "> [Verse Content]\n\n-- [Citation]"
4. Create a JSON object with the following structure:
   ```json
   {
     "book": "...",
     "chapter": "...",
     "verse": "...",
     "text_en": "...",
     "text_localized": "..."
   }
   ```
   Write this JSON object to a file named "info.json" in the current directory (`{{ run_dir }}`).
   - You MUST use a tool to write this file.
5. After creating both files, output the result JSON strictly.

## Result Format
Output the final result as a valid JSON object in a ```json code block.
The JSON must look like this:
{
  "text_file_path": "{{ run_dir }}/text.md",
  "info_file_path": "{{ run_dir }}/info.json"
}
