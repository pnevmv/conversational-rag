import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from src.rag.dense_retriever import DenseRetriever, _cache_paths, QUERY_PREFIX


class TestCachePaths(unittest.TestCase):

    def test_path_contains_model_name(self):
        cache_dir = Path("/tmp/cache")
        _, emb = _cache_paths("BAAI/bge-small-en-v1.5", None, cache_dir)
        self.assertIn("bge-small", str(emb))

    def test_domain_suffix(self):
        cache_dir = Path("/tmp/cache")
        spans, _ = _cache_paths("BAAI/bge-small-en-v1.5", "dmv", cache_dir)
        self.assertIn("_dmv", str(spans))

    def test_no_domain_no_suffix(self):
        cache_dir = Path("/tmp/cache")
        spans, _ = _cache_paths("BAAI/bge-small-en-v1.5", None, cache_dir)
        self.assertNotIn("_dmv", str(spans))


class TestDenseRetrieverWithMock(unittest.TestCase):
    """Test retrieval logic without loading the real model or data."""

    def _make_retriever_with_fake_index(self, n=10, dim=4):
        retriever = DenseRetriever.__new__(DenseRetriever)
        retriever._model_name = "BAAI/bge-small-en-v1.5"
        retriever._domain = None
        retriever._data_dir = None
        retriever._cache_dir = Path("/tmp")

        retriever._spans = [
            {"doc_id": f"doc_{i}", "id_sp": str(i), "title": f"Title {i}",
             "section_title": "", "text": f"span text {i}"}
            for i in range(n)
        ]
        rng = np.random.default_rng(42)
        emb = rng.random((n, dim)).astype(np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        retriever._embeddings = emb / norms

        mock_model = MagicMock()
        def fake_encode(text, **kwargs):
            # Return a fixed query embedding that matches span 3 best
            v = retriever._embeddings[3].copy()
            return v
        mock_model.encode = fake_encode
        retriever._model = mock_model

        return retriever

    def test_retrieve_returns_top_k(self):
        retriever = self._make_retriever_with_fake_index()
        results = retriever.retrieve("any query", top_k=5)
        self.assertEqual(len(results), 5)

    def test_retrieve_result_keys(self):
        retriever = self._make_retriever_with_fake_index()
        results = retriever.retrieve("any query", top_k=1)
        required = {"rank", "doc_id", "id_sp", "title", "section_title", "text", "score"}
        self.assertTrue(required.issubset(results[0].keys()))

    def test_retrieve_rank_1_is_highest_score(self):
        retriever = self._make_retriever_with_fake_index()
        results = retriever.retrieve("any query", top_k=5)
        # rank 1 should have the highest score
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_retrieve_best_match(self):
        retriever = self._make_retriever_with_fake_index()
        # Our fake encode always returns embeddings[3], so span 3 should be rank 1
        results = retriever.retrieve("any query", top_k=1)
        self.assertEqual(results[0]["doc_id"], "doc_3")

    def test_corpus_size(self):
        retriever = self._make_retriever_with_fake_index(n=7)
        self.assertEqual(retriever.corpus_size, 7)

    def test_query_prefix_applied(self):
        retriever = self._make_retriever_with_fake_index()
        captured = []
        original_encode = retriever._model.encode

        def capturing_encode(text, **kwargs):
            captured.append(text)
            return original_encode(text, **kwargs)

        retriever._model.encode = capturing_encode
        retriever.retrieve("what is insurance?", top_k=1)
        self.assertTrue(captured[0].startswith(QUERY_PREFIX))


class TestDenseRetrieverCacheRoundtrip(unittest.TestCase):
    """Test that save/load cache preserves spans and embeddings."""

    def test_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            spans = [{"doc_id": "d1", "id_sp": "1", "title": "T", "section_title": "", "text": "hello"}]
            embeddings = np.array([[0.5, 0.5]], dtype=np.float32)

            spans_path, emb_path = _cache_paths("BAAI/bge-small-en-v1.5", None, cache_dir)
            with open(spans_path, "w") as f:
                json.dump(spans, f)
            np.save(str(emb_path), embeddings)

            # Now build a retriever that loads from cache
            retriever = DenseRetriever(cache_dir=cache_dir)

            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.5, 0.5], dtype=np.float32)
            retriever._model = mock_model

            retriever._build_index()

            self.assertEqual(len(retriever._spans), 1)
            self.assertEqual(retriever._spans[0]["doc_id"], "d1")
            np.testing.assert_array_equal(retriever._embeddings, embeddings)


if __name__ == "__main__":
    unittest.main()
