import re

class InputValidator:
    def __init__(self):
        # Basic list of restricted words (profanity, system commands)
        self.restricted_words = ["hack", "exploit", "bypass", "nsfw"] 
        
        # Common prompt injection signatures
        self.injection_signatures = [
            "ignore all previous",
            "you are now",
            "system prompt",
            "forget your instructions"
        ]

    # Run validation checks
    def validate(self, user_input: str) -> tuple[bool, str]:

        user_input = user_input.strip()

        # Empty Check
        if not user_input:
            return False, "Input cannot be empty."

        # Length Check
        if len(user_input) > 200:
            return False, "Input is too long. Please keep your query under 200 characters."

        # Meaningless/Gibberish Check (Must contain at least one actual word)
        # Matches at least one sequence of 2 or more letters
        if not re.search(r'[a-zA-Z]{2,}', user_input):
            return False, "Input appears meaningless. Please ask a valid question about a stock."

        # Character Sanitization (Blocks excessive weird symbols like SQLi attempts)
        # Allows letters, numbers, spaces, and basic punctuation
        if not re.match(r'^[a-zA-Z0-9\s\.\,\?\'\"\-\:\$\%\&]+$', user_input):
            return False, "Input contains invalid special characters. Please use standard text."

        # Inappropriate Content Check
        input_lower = user_input.lower()
        for word in self.restricted_words:
            if word in input_lower:
                return False, f"Input contains restricted vocabulary ('{word}')."

        # Prompt Injection Check
        for signature in self.injection_signatures:
            if signature in input_lower:
                return False, "Prompt injection attempt detected. Request blocked."

        return True, ""