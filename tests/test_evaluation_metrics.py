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
