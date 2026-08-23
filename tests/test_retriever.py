import unittest

from src.rag.retriever import BM25Retriever, _tokenize


class TestTokenize(unittest.TestCase):

    def test_lowercases(self):
        self.assertEqual(_tokenize("Hello World"), ["hello", "world"])

    def test_strips_punctuation(self):
        self.assertEqual(_tokenize("don't do that!"), ["don", "t", "do", "that"])

    def test_empty(self):
        self.assertEqual(_tokenize(""), [])

    def test_numbers_kept(self):
        self.assertIn("42", _tokenize("section 42 applies"))


class TestBM25Retriever(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.retriever = BM25Retriever()

    def test_corpus_size(self):
        self.assertGreater(self.retriever.corpus_size, 0)

    def test_retrieve_returns_top_k(self):
        results = self.retriever.retrieve("insurance registration dmv", top_k=5)
        self.assertEqual(len(results), 5)

    def test_retrieve_result_keys(self):
        results = self.retriever.retrieve("driver license", top_k=1)
        self.assertEqual(len(results), 1)
        required_keys = {"rank", "doc_id", "id_sp", "title", "text", "score"}
        self.assertTrue(required_keys.issubset(results[0].keys()))

    def test_retrieve_ranks_are_ordered(self):
        results = self.retriever.retrieve("vehicle registration", top_k=5)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_retrieve_rank_starts_at_one(self):
        results = self.retriever.retrieve("license plate", top_k=3)
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[2]["rank"], 3)

    def test_relevant_result_for_dmv_query(self):
        # A DMV-specific query should retrieve DMV documents
        results = self.retriever.retrieve("vehicle registration dmv", top_k=5)
        doc_ids = [r["doc_id"] for r in results]
        # At least one result should be from a DMV document
        dmv_hits = [d for d in doc_ids if "dmv" in d.lower()
                    or any(kw in d.lower() for kw in ["registr", "vehicle", "dmv", "license", "driver"])]
        self.assertGreater(len(dmv_hits), 0)


if __name__ == "__main__":
    unittest.main()
