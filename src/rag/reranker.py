"""Cross-encoder reranker using BAAI/bge-reranker-base."""
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RERANKER_MODEL = "BAAI/bge-reranker-base"
MAX_TOKENS = 512


class RerankerCache:
    def __init__(self, cache_dir: Path) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, query: str, text: str) -> Path:
        key = hashlib.sha256(f"{query}\x00{text}".encode()).hexdigest()
        return self._dir / f"{key}.json"

    def get(self, query: str, text: str) -> Optional[float]:
        p = self._path(query, text)
        if p.exists():
            try:
                return float(json.loads(p.read_text(encoding="utf-8"))["score"])
            except Exception:
                pass
        return None

    def put(self, query: str, text: str, score: float) -> None:
        p = self._path(query, text)
        p.write_text(json.dumps({"score": score}), encoding="utf-8")


class Reranker:
    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        from sentence_transformers import CrossEncoder

        print(f"  Loading cross-encoder {RERANKER_MODEL}...")
        self.model = CrossEncoder(RERANKER_MODEL, max_length=MAX_TOKENS)
        self._cache: Optional[RerankerCache] = (
            RerankerCache(cache_dir) if cache_dir is not None else None
        )
        self.n_truncated = 0

    def _count_tokens(self, query: str, text: str) -> int:
        enc = self.model.tokenizer(
            query,
            text,
            add_special_tokens=True,
            return_attention_mask=False,
            return_token_type_ids=False,
        )
        return len(enc["input_ids"])

    def rerank_many(
        self,
        queries: List[str],
        candidates_per_query: List[List[Dict[str, Any]]],
        top_k: int = 5,
        batch_size: int = 256,
    ) -> List[Tuple[List[Dict[str, Any]], float]]:
        """Rerank candidates for many queries in one batched forward pass.

        Returns a list of (top_k_candidates, top_reranker_score) per query.
        """
        # Gather all (query, text) pairs, check cache
        all_pairs: List[Tuple[str, str]] = []
        pair_keys: List[Tuple[int, int]] = []
        cached: Dict[Tuple[int, int], float] = {}

        for qi, (query, candidates) in enumerate(zip(queries, candidates_per_query)):
            for ci, cand in enumerate(candidates):
                text = cand.get("text", "")
                score = self._cache.get(query, text) if self._cache else None
                if score is not None:
                    cached[(qi, ci)] = score
                else:
                    if self._count_tokens(query, text) > MAX_TOKENS:
                        self.n_truncated += 1
                    all_pairs.append((query, text))
                    pair_keys.append((qi, ci))

        # Batch score uncached
        fresh: Dict[Tuple[int, int], float] = {}
        if all_pairs:
            raw = self.model.predict(
                all_pairs, batch_size=batch_size, show_progress_bar=True
            )
            for (qi, ci), score, (query, text) in zip(pair_keys, raw, all_pairs):
                s = float(score)
                fresh[(qi, ci)] = s
                if self._cache:
                    self._cache.put(query, text, s)

        # Build per-query results
        results: List[Tuple[List[Dict[str, Any]], float]] = []
        for qi, (_, candidates) in enumerate(zip(queries, candidates_per_query)):
            scores_for_q = [
                cached.get((qi, ci), fresh.get((qi, ci), float("-inf")))
                for ci in range(len(candidates))
            ]
            top = sorted(enumerate(scores_for_q), key=lambda x: x[1], reverse=True)[
                :top_k
            ]
            ranked: List[Dict[str, Any]] = []
            for new_rank, (ci, score) in enumerate(top, start=1):
                c = dict(candidates[ci])
                c["rank"] = new_rank
                c["reranker_score"] = score
                ranked.append(c)
            top_score = ranked[0]["reranker_score"] if ranked else 0.0
            results.append((ranked, top_score))

        return results
