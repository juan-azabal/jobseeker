---
paths:
  - "prompts/**"
  - "scorer.py"
  - "parser.py"
  - "onboard.py"
---
# Prompt Management

Prompts live in prompts/*.md. They are the source of truth for LLM behavior.

When editing a prompt:
1. Edit the file in prompts/, not the Python code
2. Bump the version in the file header comment
3. Test by running the relevant module standalone
4. The Python module reads the file at runtime via a cached loader function

When creating a new LLM call in Python:
1. Create prompts/{module}-prompt.md first
2. Add a _get_{name}_prompt() cached loader in the Python module
3. Reference the prompt file path as a module-level constant

Never use f-strings for prompt templates containing JSON examples (curly braces conflict). Use .replace() with named placeholders.
