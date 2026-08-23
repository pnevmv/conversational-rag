import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from src.data.loader import load_documents


def _tokenize(text: str) -> List[str]:
    """Lowercase and split on non-alphanumeric characters."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever:
    """
    BM25-based retriever over MultiDoc2Dial document spans.

    Each span (a pre-defined text segment within a document) is treated as
    an independent retrieval unit. This mirrors the dataset's grounding
    annotations, which point to specific span IDs rather than full documents.

    The index is built lazily on the first call to retrieve().
    """

    def __init__(self, domain: Optional[str] = None, data_dir: Optional[Path] = None):
        self._domain = domain
        self._data_dir = data_dir
        self._spans: List[Dict[str, Any]] = []
        self._bm25: Optional[BM25Okapi] = None

    def _build_index(self) -> None:
        """Load all document spans and build the BM25 index."""
        docs = load_documents(domain=self._domain, data_dir=self._data_dir)

        for doc_id, doc in docs.items():
            title = doc.get("title", doc_id)
            spans = doc.get("spans", {})
            for span_id, span in spans.items():
                text = span.get("text_sp", "").strip()
                if not text:
                    continue
                self._spans.append({
                    "doc_id": doc_id,
                    "id_sp": span.get("id_sp", span_id),
                    "title": title,
                    "text": text,
                    "section_title": span.get("title", ""),
                })

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
