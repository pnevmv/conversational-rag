from pathlib import Path
from typing import Any, Dict, List, Optional

from src.rag.retriever import BM25Retriever
from src.rag.dense_retriever import DenseRetriever

# Standard RRF constant. Controls how much weight low-ranked results get.
# k=60 is the value used in the original Cormack et al. (2009) paper.
RRF_K = 60


def reciprocal_rank_fusion(
    rankings: List[List[Dict[str, Any]]],
    k: int = RRF_K,
) -> List[Dict[str, Any]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Each span is identified by (doc_id, id_sp). Its RRF score is the sum
    of 1 / (k + rank) across all rankers that retrieved it. Spans that
    appear in several lists are boosted; spans from a single list are
    ranked by how highly that list placed them.

    Args:
        rankings: List of ranked result lists, each from a different retriever.
                  Each result must have doc_id, id_sp, and the retriever-
                  specific metadata (title, section_title, text, score).
        k:        RRF constant (default 60).

    Returns:
        Merged list sorted by descending RRF score.
    """
    scores: Dict[tuple, float] = {}
    spans: Dict[tuple, Dict[str, Any]] = {}

    for ranking in rankings:
        for result in ranking:
            key = (result["doc_id"], str(result["id_sp"]))
            rank = result["rank"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in spans:
                spans[key] = result

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [
        {
            **spans[key],
            "rank": rank,
            "rrf_score": rrf_score,
        }
        for rank, (key, rrf_score) in enumerate(merged, start=1)
    ]


class HybridRetriever:
    """
    Hybrid retriever combining BM25 and dense retrieval via Reciprocal Rank Fusion.

    Each ranker retrieves pool_factor × top_k candidates independently.
    Their ranked lists are merged with RRF and the final top_k are returned.

    Using a larger pool per ranker (pool_factor > 1) ensures that spans
    ranked just outside the final top_k in one system can still be rescued
    by a high rank in the other.
    """

    def __init__(
        self,
        domain: Optional[str] = None,
        data_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        pool_factor: int = 3,
        rrf_k: int = RRF_K,
    ):
        self._pool_factor = pool_factor
        self._rrf_k = rrf_k
        self._bm25 = BM25Retriever(domain=domain, data_dir=data_dir)
        self._dense = DenseRetriever(domain=domain, data_dir=data_dir, cache_dir=cache_dir)

    def build_index(self) -> None:
        """Pre-build both indexes (optional; retrieve() builds lazily otherwise)."""
        _ = self._bm25.corpus_size
        _ = self._dense.corpus_size

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Return top_k spans by RRF score.

        Each result contains the original span fields (doc_id, id_sp, title,
        section_title, text, score from the first ranker that found it) plus
        rrf_score and rank.
        """
        pool = top_k * self._pool_factor

        bm25_results = self._bm25.retrieve(query, top_k=pool)
        dense_results = self._dense.retrieve(query, top_k=pool)

        merged = reciprocal_rank_fusion(
            [bm25_results, dense_results], k=self._rrf_k
        )

        return merged[:top_k]

    @property
    def corpus_size(self) -> int:
        return self._dense.corpus_size
