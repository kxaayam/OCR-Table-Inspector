import unittest

from Functions.vision_matching import (
    CandidateText, lexical_tokens, multiset_f1, normalize_text,
    numeric_tokens, rank_candidates, visible_text,
)


class MatchingTests(unittest.TestCase):
    def test_normalization_and_visible_html(self):
        self.assertEqual(normalize_text(visible_text(
            "<td>Caf&eacute;&nbsp; TOTAL</td>")), "café total")

    def test_token_extraction(self):
        text = "Arts & Sciences: 1,234, -5.50 and 20%"
        self.assertEqual(lexical_tokens(text), ["arts", "sciences", "and"])
        self.assertEqual(numeric_tokens(text), ["1234", "-5.50", "20%"])

    def test_multiset_f1(self):
        self.assertEqual(multiset_f1(["a", "a", "b"], ["a", "b", "b"]),
                         2 / 3)

    def test_agreement_accepts(self):
        result = rank_candidates(
            "<table><tr><td>Arts</td><td>12</td></tr></table>",
            [CandidateText("a", "Arts 12"), CandidateText("b", "Science 14")])
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["selected"], "a")

    def test_disagreement_is_unresolved(self):
        result = rank_candidates(
            "<table><td>Arts</td><td>12</td></table>",
            [CandidateText("a", "Arts 99"), CandidateText("b", "Other 12")])
        self.assertEqual(result["status"], "unresolved")

    def test_missing_numeric_is_unresolved(self):
        result = rank_candidates("<table><td>Arts</td></table>",
                                 [CandidateText("a", "Arts")])
        self.assertEqual(result["status"], "unresolved")

    def test_tie_is_unresolved(self):
        result = rank_candidates(
            "<table><td>Arts</td><td>12</td></table>",
            [CandidateText("a", "Arts 12"), CandidateText("b", "Arts 12")])
        self.assertEqual(result["status"], "unresolved")


if __name__ == "__main__":
    unittest.main()
