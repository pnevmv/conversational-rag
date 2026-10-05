import unittest

from src.evaluation.metrics import compute_metrics, exact_match, token_f1


class TestExactMatch(unittest.TestCase):

    def test_identical(self):
        self.assertEqual(exact_match("Yes", "Yes"), 1)

    def test_case_insensitive(self):
        self.assertEqual(exact_match("YES", "yes"), 1)

    def test_punctuation_ignored(self):
        self.assertEqual(exact_match("Yes.", "Yes"), 1)

    def test_articles_ignored(self):
        self.assertEqual(exact_match("the answer is yes", "answer is yes"), 1)

    def test_whitespace_normalized(self):
        self.assertEqual(exact_match("  yes  ", "yes"), 1)

    def test_mismatch(self):
        self.assertEqual(exact_match("yes", "no"), 0)

    def test_empty_strings(self):
        self.assertEqual(exact_match("", ""), 1)

    def test_one_empty(self):
        self.assertEqual(exact_match("", "yes"), 0)


class TestTokenF1(unittest.TestCase):

    def test_identical(self):
        self.assertAlmostEqual(token_f1("yes it is", "yes it is"), 1.0)

    def test_partial_overlap(self):
        f1 = token_f1("yes it is correct", "yes it is")
        self.assertGreater(f1, 0.0)
        self.assertLess(f1, 1.0)

    def test_no_overlap(self):
        self.assertAlmostEqual(token_f1("hello world", "foo bar"), 0.0)

    def test_both_empty(self):
        self.assertAlmostEqual(token_f1("", ""), 1.0)

    def test_prediction_empty(self):
        self.assertAlmostEqual(token_f1("", "yes"), 0.0)

    def test_reference_empty(self):
        self.assertAlmostEqual(token_f1("yes", ""), 0.0)

    def test_symmetry(self):
        a = "you need to bring your documents"
        b = "bring your documents to the office"
        self.assertAlmostEqual(token_f1(a, b), token_f1(b, a), places=6)

    def test_f1_range(self):
        f1 = token_f1("some partial answer here", "some reference answer here")
        self.assertGreaterEqual(f1, 0.0)
        self.assertLessEqual(f1, 1.0)


class TestComputeMetrics(unittest.TestCase):

    def test_returns_both_keys(self):
        result = compute_metrics("yes", "yes")
        self.assertIn("exact_match", result)
        self.assertIn("f1", result)

    def test_perfect_score(self):
        result = compute_metrics("yes it is", "yes it is")
        self.assertEqual(result["exact_match"], 1.0)
        self.assertAlmostEqual(result["f1"], 1.0)

    def test_zero_score(self):
        result = compute_metrics("hello world", "foo bar")
        self.assertEqual(result["exact_match"], 0.0)
        self.assertAlmostEqual(result["f1"], 0.0)


if __name__ == "__main__":
    unittest.main()


# LLM judge helpers

from src.evaluation.judge import build_prompt, parse_verdict, rule_verdict


def test_parse_verdict_reads_json_inside_text():
    v = parse_verdict('Sure. {"verdict": "Partial", "supported": "true", "reason": "misses the fee"}')
    assert v == {"verdict": "partial", "supported": True, "reason": "misses the fee"}
    assert parse_verdict("no json here") is None
    assert parse_verdict('{"verdict": "maybe"}') is None


def test_abstentions_are_scored_by_rule():
    abst = "Unfortunately, no relevant information is found."
    assert rule_verdict({"is_unanswerable": True}, abst)["verdict"] == "correct"
    assert rule_verdict({"is_unanswerable": True}, "You need form MV-82.")["verdict"] == "incorrect"
    assert rule_verdict({"is_unanswerable": False}, abst)["verdict"] == "incorrect"
    assert rule_verdict({"is_unanswerable": False}, "")["verdict"] == "incorrect"
    assert rule_verdict({"is_unanswerable": False}, "You need form MV-82.") is None


def test_judge_prompt_contains_all_parts():
    ex = {"question": "Do I need insurance?", "reference_answer": "Yes, liability insurance.",
          "dialogue_history": [{"role": "user", "utterance": "Hi"}, {"role": "agent", "utterance": "Hello"}]}
    p = build_prompt(ex, "Yes, you need insurance.", "Section text", "Retrieved context")
    for part in ("Customer: Hi", "Agent: Hello", "Do I need insurance?", "Yes, liability insurance.",
                 "Section text", "Retrieved context", "Yes, you need insurance."):
        assert part in p
    assert "answered without documents" in build_prompt(ex, "Yes.", "Section text")
    assert build_prompt(ex, "Yes.", "S", "§" * 10000).count("§") == 6000
