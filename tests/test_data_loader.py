import unittest
from src.data.loader import load_qa_pairs


class TestDataLoader(unittest.TestCase):
    """Unit tests for dataset loading and QA pair extraction."""

    def test_load_qa_pairs_structure_and_count(self):
        """Verify load_qa_pairs returns the requested count with required fields."""
        pairs = load_qa_pairs(split="validation", max_examples=5)
        self.assertEqual(len(pairs), 5)

        required_keys = {
            "example_id",
            "domain",
            "dialogue_id",
            "turn_id",
            "question",
            "reference_answer",
            "document_id",
            "grounding",
        }
        for item in pairs:
            self.assertTrue(required_keys.issubset(item.keys()))
            self.assertTrue(len(item["question"]) > 0)
            self.assertTrue(len(item["reference_answer"]) > 0)

    def test_load_qa_pairs_determinism(self):
        """Verify that load_qa_pairs produces deterministic ordering across repeated calls."""
        run1 = load_qa_pairs(split="validation", max_examples=10)
        run2 = load_qa_pairs(split="validation", max_examples=10)

        ids1 = [p["example_id"] for p in run1]
        ids2 = [p["example_id"] for p in run2]

        self.assertEqual(ids1, ids2)


if __name__ == "__main__":
    unittest.main()
