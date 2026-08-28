import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from src.data.loader import load_sections


def _tokenize(text: str) -> List[str]:
    """Lowercase and split on non-alphanumeric characters."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever:
    """
    BM25-based retriever over MultiDoc2Dial document sections.

    Each section (heading + all following content spans until the next heading)
    is the retrieval unit. This avoids indexing bare heading spans that carry
    no answer text. span_ids on each result lists all individual span IDs in
    the section, so Recall@K can be checked against the dataset's per-span
    grounding annotations.

    The index is built lazily on the first call to retrieve().
    """

    def __init__(self, domain: Optional[str] = None, data_dir: Optional[Path] = None):
        self._domain = domain
        self._data_dir = data_dir
        self._spans: List[Dict[str, Any]] = []
        self._bm25: Optional[BM25Okapi] = None

    def _build_index(self) -> None:
        """Load all document sections and build the BM25 index."""
        self._spans = load_sections(domain=self._domain, data_dir=self._data_dir)
        tokenized_corpus = [_tokenize(s["text"]) for s in self._spans]
        self._bm25 = BM25Okapi(tokenized_corpus)

    def retrieve(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the top-k spans most relevant to the query.

        Returns a list of result dicts, each containing:
            - doc_id, id_sp, title, section_title, text
            - score (BM25 score)
            - rank (1-indexed)
        """
        if self._bm25 is None:
            self._build_index()

        query_tokens = _tokenize(query)
        scores = self._bm25.get_scores(query_tokens)

        # Pair each span with its score and sort descending
        scored = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]

        results = []
        for rank, (idx, score) in enumerate(scored, start=1):
            span = self._spans[idx]
            results.append({
                "rank": rank,
                "doc_id": span["doc_id"],
                "id_sp": span["id_sp"],
                "span_ids": span.get("span_ids", [str(span["id_sp"])]),
                "title": span["title"],
                "section_title": span["section_title"],
                "text": span["text"],
                "score": float(score),
            })

        return results

    @property
    def corpus_size(self) -> int:
        """Number of indexed spans (builds index if needed)."""
        if self._bm25 is None:
            self._build_index()
        return len(self._spans)
