import json
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentence_transformers import SentenceTransformer

from src.data.loader import load_documents

MODEL_NAME = "BAAI/bge-small-en-v1.5"

# BGE models use a query instruction prefix for retrieval tasks.
# Passage embeddings are built without the prefix.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _cache_paths(model_name: str, domain: Optional[str], cache_dir: Path):
    safe = model_name.replace("/", "_")
    suffix = f"_{domain}" if domain else ""
    return (
        cache_dir / f"dense_spans{suffix}.json",
        cache_dir / f"dense_embeddings_{safe}{suffix}.npy",
    )


class DenseRetriever:
    """
    Dense retriever using BGE embeddings and exact cosine similarity.

    Passages are embedded once and cached to disk. Retrieval is a single
    matrix-vector dot product (embeddings are L2-normalised, so dot product
    equals cosine similarity).

    The BGE query instruction prefix is applied to queries but not to
    passages, matching the model's recommended usage for asymmetric retrieval.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        domain: Optional[str] = None,
        data_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
    ):
        self._model_name = model_name
        self._domain = domain
        self._data_dir = data_dir
        project_root = Path(__file__).resolve().parent.parent.parent
        self._cache_dir = cache_dir or (project_root / "data" / "cache")
        self._spans: Optional[List[Dict]] = None
        self._embeddings: Optional[np.ndarray] = None
        self._model: Optional[SentenceTransformer] = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def _build_index(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        spans_path, emb_path = _cache_paths(self._model_name, self._domain, self._cache_dir)

        if spans_path.exists() and emb_path.exists():
            print(f"Loading cached dense index ({spans_path.parent.name})...")
            with open(spans_path, encoding="utf-8") as f:
                self._spans = json.load(f)
            self._embeddings = np.load(str(emb_path))
            print(f"Loaded {len(self._spans):,} spans.")
            return

        print("Loading documents...")
        docs = load_documents(domain=self._domain, data_dir=self._data_dir)

        spans = []
        for doc_id, doc in docs.items():
            title = doc.get("title", doc_id)
            for span_id, span in doc.get("spans", {}).items():
                text = span.get("text_sp", "").strip()
                if not text:
                    continue
                spans.append({
                    "doc_id": doc_id,
                    "id_sp": span.get("id_sp", span_id),
                    "title": title,
                    "section_title": span.get("title", ""),
                    "text": text,
                })

        self._spans = spans
        texts = [s["text"] for s in spans]

        print(f"Loading model: {self._model_name}")
        model = self._get_model()

        print(f"Embedding {len(texts):,} spans (this runs once and is cached)...")
        self._embeddings = model.encode(
            texts,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=True,
            convert_to_numpy=True,
        ).astype(np.float32)

        print("Saving index to cache...")
        with open(spans_path, "w", encoding="utf-8") as f:
            json.dump(spans, f, ensure_ascii=False)
        np.save(str(emb_path), self._embeddings)
        print(f"Index saved: {len(spans):,} spans, shape {self._embeddings.shape}.")

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Return top_k spans by cosine similarity to the query.

        Result dicts contain: rank, doc_id, id_sp, title, section_title,
        text, score (cosine similarity in [-1, 1]).
        """
        if self._embeddings is None:
            self._build_index()

        query_emb = self._get_model().encode(
            QUERY_PREFIX + query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)

        scores = self._embeddings @ query_emb  # (N,)

        top_indices = np.argpartition(scores, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [
            {
                "rank": rank,
                "doc_id": self._spans[idx]["doc_id"],
                "id_sp": self._spans[idx]["id_sp"],
                "title": self._spans[idx]["title"],
                "section_title": self._spans[idx]["section_title"],
                "text": self._spans[idx]["text"],
                "score": float(scores[idx]),
            }
            for rank, idx in enumerate(top_indices, start=1)
        ]

    @property
    def corpus_size(self) -> int:
        if self._embeddings is None:
            self._build_index()
        return len(self._spans)
