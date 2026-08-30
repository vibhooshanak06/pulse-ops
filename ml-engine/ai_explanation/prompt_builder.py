"""
Prompt builder.

Converts the structured evidence object into a prompt for the LLM.
The prompt explicitly instructs the model to:
  - Only reason over supplied evidence
  - Never invent root causes
  - Express confidence as a score
  - State uncertainty when evidence is insufficient

Phase 13 implementation.
"""

# TODO: Phase 13
