import re
from spellchecker import SpellChecker
from better_profanity import profanity

class InputValidator:
    def __init__(self):
        # Common prompt injection signatures
        self.injection_signatures = [
            "ignore all previous",
            "you are now",
            "system prompt",
            "forget your instructions"
        ]

        # Initialize a dictionary
        self.spell = SpellChecker()

        # Initialize a profanity filter
        profanity.load_censor_words()
    
    # Evaluate if the text has a sufficient ratio of valid English words forgiving ALL-CAPS words)
    def _is_meaningful(self, user_input: str) -> bool:

        # Extract all alphabetic words from the input
        words = re.findall(r'\b[a-zA-Z]+\b', user_input)
        
        if not words:
            return False

        # Filter out probable tickers (all caps) and single-letter words
        standard_words = [w.lower() for w in words if not w.isupper() and len(w) > 1]

        # If the user ONLY typed a ticker, let it pass
        if not standard_words and words:
            return True

        # Check how many of the standard words exist in the English dictionary
        known_words = self.spell.known(standard_words)

        # Calculate the ratio of valid words
        valid_ratio = len(known_words) / len(standard_words)

        # Require at least one valid English word, AND a 40% valid word ratio
        if len(known_words) >= 1 and valid_ratio >= 0.4:
            return True

        return False


    # Run validation checks
    def validate(self, user_input: str) -> tuple[bool, str]:

        user_input = user_input.strip()

        # Empty Check
        if not user_input:
            return False, "Input cannot be empty."

        # Length Check
        if len(user_input) > 200:
            return False, "Input is too long. Please keep your query under 200 characters."

        # Gibberish Check
        if not self._is_meaningful(user_input):
            return False, "Input appears meaningless or contains too much gibberish. Please use standard English."

        # Character Sanitization
        if not re.match(r'^[a-zA-Z0-9\s\.\,\?\'\"\-\:\$\%\&]+$', user_input):
            return False, "Input contains invalid special characters. Please use standard text."

        # Inappropriate Content Check
        if profanity.contains_profanity(user_input):
            return False, "Inappropriate language detected (including obfuscated text)."

        # Prompt Injection Check
        input_lower = user_input.lower()
        for signature in self.injection_signatures:
            if signature in input_lower:
                return False, "Prompt injection attempt detected. Request blocked."

        return True, ""