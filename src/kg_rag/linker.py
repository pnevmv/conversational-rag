"""Entity linking: query text -> ranked KG entities.

Two candidate generators over the entity surface forms (entity name, resolved mention
names, aliases; see src.kg_rag.graph_index):
  - dense: bge-small (the Step 4 dense model), cosine between the query (with the BGE query
    prefix) and every surface form; an entity scores its best form;
  - BM25 over one short document per entity (its forms, stopwords removed).
The two rankings are fused with RRF (k=60, as in the Step 4 hybrid retriever).

Filters, both optional:
  - domain: when the predicted domain is confident, keep entities seen in that domain;
  - hubs: skip entities whose degree (typed entity relations) is above a cap, by default the
    99th percentile of the scope (16 in the full graph), e.g. "VA health care" (99).
"""
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from src.kg_rag.graph_index import OUT_DIR, load_entities
from src.rag.dense_retriever import MODEL_NAME, QUERY_PREFIX
from src.rag.hybrid_retriever import RRF_K

POOL = 100            # candidates per generator before fusion
HUB_PERCENTILE = 99

STOPWORDS = frozenset("""
a an the and or of to in on for with by at from as is are was were be been being do does did
i me my we our you your he she it its they them their this that these those there here what
which who whom how when where why can could would should will shall may might must have has had
not no yes if then than so but about into over under any all some more most other such only own
same just also very get got go going need want know like please thanks thank ok okay hi hello
""".split())


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


class EntityLinker:
    def __init__(self, scope: str = "full", hub_percentile: Optional[float] = HUB_PERCENTILE,
                 cache_dir: Path = OUT_DIR):
        from rank_bm25 import BM25Okapi

        self.entities = load_entities(scope)
        self.by_id = {e["entity_id"]: e for e in self.entities}
        degrees = np.array([e["degree"] for e in self.entities])
        self.hub_cap = None if hub_percentile is None else float(np.percentile(degrees, hub_percentile))
        self._domains = [set(e["domains"]) for e in self.entities]

        self._form_entity = np.array([i for i, e in enumerate(self.entities) for _ in e["forms"]])
        forms = [f for e in self.entities for f in e["forms"]]
        self._model = None
        emb_path = cache_dir / f"entity_forms_{scope}_{MODEL_NAME.replace('/', '_')}.npy"
        if emb_path.exists() and np.load(emb_path, mmap_mode="r").shape[0] == len(forms):
            self._form_emb = np.load(emb_path)
        else:
            self._form_emb = self.model.encode(forms, batch_size=256, normalize_embeddings=True,
                                               convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
            np.save(emb_path, self._form_emb)
        self._bm25 = BM25Okapi([tokenize(" ".join(e["forms"])) or ["_"] for e in self.entities])

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    def is_hub(self, entity: Dict[str, Any]) -> bool:
        return self.hub_cap is not None and entity["degree"] > self.hub_cap

    def _allowed(self, domain: Optional[str], skip_hubs: bool) -> np.ndarray:
        mask = np.ones(len(self.entities), dtype=bool)
        if domain:
            mask &= np.array([domain in d for d in self._domains])
        if skip_hubs and self.hub_cap is not None:
            mask &= np.array([e["degree"] <= self.hub_cap for e in self.entities])
        return mask

    def encode(self, queries: Iterable[str]) -> np.ndarray:
        return self.model.encode([QUERY_PREFIX + q for q in queries], batch_size=64, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False).astype(np.float32)

    def dense_scores(self, query_emb: np.ndarray) -> np.ndarray:
        form_scores = self._form_emb @ query_emb
        scores = np.full(len(self.entities), -np.inf, dtype=np.float32)
        np.maximum.at(scores, self._form_entity, form_scores)
        return scores

    def link(self, query: str, k: int = 10, domain: Optional[str] = None, skip_hubs: bool = True,
             method: str = "rrf", query_emb: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """Top-k entities for the query. method: rrf | dense | bm25."""
        allowed = self._allowed(domain, skip_hubs)
        rankings = []
        if method in ("rrf", "dense"):
            emb = query_emb if query_emb is not None else self.encode([query])[0]
            dense = np.where(allowed, self.dense_scores(emb), -np.inf)
            rankings.append(("dense", dense))
        if method in ("rrf", "bm25"):
            tokens = tokenize(query)
            bm25 = self._bm25.get_scores(tokens) if tokens else np.zeros(len(self.entities))
            bm25 = np.where(allowed & (bm25 > 0), bm25, -np.inf)
            rankings.append(("bm25", bm25))

        fused: Dict[int, Dict[str, Any]] = {}
        for name, scores in rankings:
            n_valid = int(np.isfinite(scores).sum())
            pool = min(POOL, n_valid)
            if pool == 0:
                continue
            top = np.argpartition(-scores, pool - 1)[:pool]
            top = top[np.argsort(-scores[top])]
            for rank, i in enumerate(top, start=1):
                row = fused.setdefault(int(i), {"rrf": 0.0})
                row["rrf"] += 1.0 / (RRF_K + rank)
                row[f"{name}_rank"] = rank
                row[f"{name}_score"] = float(scores[i])
        ranked = sorted(fused.items(), key=lambda kv: -kv[1]["rrf"])[:k]
        out = []
        for rank, (i, row) in enumerate(ranked, start=1):
            e = self.entities[i]
            out.append({"rank": rank, "entity_id": e["entity_id"], "name": e["name"], "type": e["type"],
                        "degree": e["degree"], "score": row["rrf"],
                        **{key: v for key, v in row.items() if key != "rrf"}})
        return out

    def link_many(self, queries: List[str], query_embs: List[np.ndarray], k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Link several texts of one turn (e.g. raw and rewritten) and fuse the rankings by RRF."""
        fused: Dict[str, Dict[str, Any]] = {}
        for q, emb in zip(queries, query_embs):
            for l in self.link(q, k=POOL, query_emb=emb, **kwargs):
                row = fused.setdefault(l["entity_id"], {**l, "score": 0.0})
                row["score"] += 1.0 / (RRF_K + l["rank"])
        ranked = sorted(fused.values(), key=lambda l: -l["score"])[:k]
        return [{**l, "rank": rank} for rank, l in enumerate(ranked, start=1)]
