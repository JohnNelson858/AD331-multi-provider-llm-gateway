"""Fixed fifty-word prompt shared by offline and opt-in live QA."""
# Numbered technical identifiers intentionally tokenize into multiple pieces.
# Sufficient length keeps chat-framing overhead small for the live comparison.
TOKEN_PROMPT = ' '.join(f'microcontroller{i:02d}' for i in range(1, 51))
