import unittest
from actions.base_form import LanguageHelper
from typing import Tuple

class TestLanguageHelper(unittest.TestCase):
    """Test cases for LanguageHelper class."""

    def setUp(self):
        """Set up test cases."""
        self.lang_helper = LanguageHelper()

    def test_detect_language(self):
        """Test language detection for different inputs."""
        test_cases = [
            ("Hello world", "en"),
            ("नमस्ते संसार", "ne"),
            ("Hello नमस्ते", "ne"),  # Mixed but more Devanagari
            ("", "en"),  # Empty string
            ("123", "en"),  # Numbers only
            ("   ", "en"),  # Whitespace only
        ]
        
        for text, expected in test_cases:
            with self.subTest(text=text):
                result = self.lang_helper.detect_language(text)
                self.assertEqual(result, expected)

    def test_fuzzy_match_score(self):
        """Test fuzzy matching scores."""
        test_cases = [
            # (input_text, target_words, expected_score, expected_match)
            ("skip", ["skip", "pass"], 100, "skip"),     # Exact match
            ("skp", ["skip", "pass"], 75, "skip"),       # Partial match
            ("pas", ["skip", "pass"], 75, "pass"),       # Partial match
            ("hello", ["skip", "pass"], 0, ""),          # No match
            ("छोड", ["छोड्नुहोस्", "छोड"], 100, "छोड"),  # Exact Nepali match
        ]
        
        for text, targets, expected_score, expected_match in test_cases:
            with self.subTest(text=text):
                score, matched_word = self.lang_helper._get_fuzzy_match_score(text, targets)
                
                # Validate score ranges
                if expected_score == 100:
                    self.assertGreaterEqual(score, 98)
                elif expected_score == 75:
                    self.assertGreaterEqual(score, 75)
                    self.assertLess(score, 98)
                else:  # expected_score == 0
                    self.assertLess(score, 75)
                
                # For high enough scores, validate matched word
                if score >= 75:
                    self.assertEqual(matched_word, expected_match)
                else:
                    self.assertEqual(matched_word, "")

    def test_skip_instruction(self):
        """Test skip instruction detection."""
        test_cases = [
            ("skip", (True, False, "skip")),      # Direct skip
            ("skp", (True, True, "skip")),        # Needs validation
            ("छोड", (True, False, "छोड")),       # Direct Nepali skip
            ("छोद", (True, True, "छोड")),        # Needs validation
            ("hello", (False, False, "")),        # Not a skip
            ("", (False, False, "")),             # Empty string
        ]
        
        for text, expected in test_cases:
            with self.subTest(text=text):
                result = self.lang_helper.is_skip_instruction(text)
                self.assertEqual(result, expected)

    def test_edge_cases(self):
        """Test edge cases and potential error conditions."""
        test_cases = [
            (None, (False, False, "")),  # None input
            ("   ", (False, False, "")),  # Whitespace only
            ("123", (False, False, "")),  # Numbers only
            ("!@#", (False, False, "")),  # Special characters
        ]
        
        for text, expected in test_cases:
            with self.subTest(text=text):
                result = self.lang_helper.is_skip_instruction(text)
                self.assertEqual(result, expected)


def run_tests():
    """Run all tests."""
    unittest.main()

if __name__ == '__main__':
    run_tests()