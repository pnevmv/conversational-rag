import unittest

from src.rag.hybrid_retriever import reciprocal_rank_fusion


def _make_result(doc_id, id_sp, rank, score=1.0):
    return {
        "doc_id": doc_id,
        "id_sp": str(id_sp),
        "rank": rank,
        "title": f"Title {doc_id}",
        "section_title": "",
        "text": f"text {doc_id} {id_sp}",
        "score": score,
    }


class TestRRF(unittest.TestCase):

    def test_single_ranking_passthrough(self):
        ranking = [_make_result("d1", "1", 1), _make_result("d2", "2", 2)]
        result = reciprocal_rank_fusion([ranking])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["doc_id"], "d1")

    def test_overlap_boosts_span(self):
        # "d1/1" appears at rank 1 in both — should beat "d2/2" which only
        # appears in one list
        r1 = [_make_result("d1", "1", 1), _make_result("d2", "2", 2)]
        r2 = [_make_result("d1", "1", 1), _make_result("d3", "3", 2)]
        merged = reciprocal_rank_fusion([r1, r2])
        self.assertEqual(merged[0]["doc_id"], "d1")
        self.assertEqual(merged[0]["id_sp"], "1")

    def test_rrf_scores_descending(self):
        r1 = [_make_result("d1", "1", 1), _make_result("d2", "2", 2), _make_result("d3", "3", 3)]
        r2 = [_make_result("d2", "2", 1), _make_result("d1", "1", 2), _make_result("d4", "4", 3)]
        merged = reciprocal_rank_fusion([r1, r2])
        scores = [r["rrf_score"] for r in merged]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_non_overlapping_rankings_combined(self):
        r1 = [_make_result("d1", "1", 1)]
        r2 = [_make_result("d2", "2", 1)]
        merged = reciprocal_rank_fusion([r1, r2])
        ids = {r["doc_id"] for r in merged}
        self.assertIn("d1", ids)
        self.assertIn("d2", ids)

    def test_rrf_score_formula(self):
        k = 60
        r1 = [_make_result("d1", "1", 1)]
        r2 = [_make_result("d1", "1", 1)]
        merged = reciprocal_rank_fusion([r1, r2], k=k)
        expected = 2 * (1.0 / (k + 1))
        self.assertAlmostEqual(merged[0]["rrf_score"], expected)

    def test_result_has_rank_field(self):
        ranking = [_make_result("d1", "1", 1), _make_result("d2", "2", 2)]
        merged = reciprocal_rank_fusion([ranking])
        self.assertEqual(merged[0]["rank"], 1)
        self.assertEqual(merged[1]["rank"], 2)

    def test_result_has_rrf_score_field(self):
        ranking = [_make_result("d1", "1", 1)]
        merged = reciprocal_rank_fusion([ranking])
        self.assertIn("rrf_score", merged[0])

    def test_empty_rankings(self):
        merged = reciprocal_rank_fusion([[], []])
        self.assertEqual(merged, [])

    def test_span_identity_by_doc_and_id_sp(self):
        # Same doc_id but different id_sp must be separate entries
        r1 = [_make_result("d1", "1", 1)]
        r2 = [_make_result("d1", "2", 1)]
        merged = reciprocal_rank_fusion([r1, r2])
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
