"""KG retrievers for dev-500 QA (Step 6, phase 2).

All start from the top-10 entities linked to the rewritten query (src.kg_rag.linker, hubs
kept). Each linked entity e gets a weight

    w(e) = link(e) * idf(e),   link(e) = its RRF linking score,
                               idf(e)  = log(1 + N / sections(e))

where N is the number of sections with at least one entity and sections(e) the number of
sections e is mentioned in: an entity mentioned everywhere (a hub) points to no section
in particular.

A. KG -> sections. A section scores the sum of the weights of the linked entities it
   mentions (ties: more linked entities, then section id). With 1-hop expansion, every
   neighbour n of a non-hub linked entity e through an entity relation also counts, with
   weight EXPAND_DECAY * link(e) * idf(n) (the maximum over its linked neighbours); hub
   neighbours are not added.
B. KG facts. Candidate facts are the entity relations of the linked entities. They are
   ranked by RRF of (i) the weight of their best linked endpoint (ties: support) and
   (ii) the cosine between the query and the fact text (bge-small); the top FACT_BUDGET
   facts are given to the generator as triples with one evidence quote each.
C. Hybrid. RRF of A's ranking and the Step 4 best ranking (Hybrid + Rewrite + Rerank,
   top-50 each); the fused top-50 is reranked by the Step 4 cross-encoder to the top-5.
"""
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.data.loader import load_sections, make_section_id
from src.kg_rag.graph_index import OUT_DIR, load_relations
from src.kg_rag.linker import EntityLinker
from src.rag.dense_retriever import MODEL_NAME
from src.rag.hybrid_retriever import RRF_K

LINK_K = 10
EXPAND_DECAY = 0.5
FACT_BUDGET = 30
POOL_K = 50


def relation_words(relation: str) -> str:
    return relation.lower().replace("_", " ")


class KGRetriever:
    def __init__(self, linker: EntityLinker, scope: str = "full"):
        self.linker = linker
        self.entities = linker.by_id
        self.relations = load_relations(scope)
        self.sections = {make_section_id(s["doc_id"], s["id_sp"]): s for s in load_sections()}

        self.section_entities: Dict[str, List[str]] = defaultdict(list)
        for e in linker.entities:
            for sid in e["section_ids"]:
                self.section_entities[sid].append(e["entity_id"])
        n = len(self.section_entities)
        self.idf = {e["entity_id"]: math.log(1 + n / max(1, len(e["section_ids"]))) for e in linker.entities}
        self.adjacent: Dict[str, List[int]] = defaultdict(list)
        for i, r in enumerate(self.relations):
            self.adjacent[r["source"]].append(i)
            self.adjacent[r["target"]].append(i)
        self._fact_emb: Optional[np.ndarray] = None
        self._scope = scope

    # --- shared ---------------------------------------------------------------------------

    def link(self, query: str, query_emb: np.ndarray, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.linker.link(query, k=LINK_K, domain=domain, skip_hubs=False, query_emb=query_emb)

    def weights(self, linked: List[Dict[str, Any]], expand: bool = False) -> Dict[str, float]:
        w = {l["entity_id"]: l["score"] * self.idf[l["entity_id"]] for l in linked}
        if expand:
            extra: Dict[str, float] = {}
            for l in linked:
                if self.linker.is_hub(self.entities[l["entity_id"]]):
                    continue
                for i in self.adjacent[l["entity_id"]]:
                    r = self.relations[i]
                    nb = r["target"] if r["source"] == l["entity_id"] else r["source"]
                    if nb in w or self.linker.is_hub(self.entities[nb]):
                        continue
                    extra[nb] = max(extra.get(nb, 0.0), EXPAND_DECAY * l["score"] * self.idf[nb])
            w.update(extra)
        return w

    def section_result(self, sid: str, rank: int, score: float, **extra) -> Dict[str, Any]:
        s = self.sections[sid]
        return {"rank": rank, "doc_id": s["doc_id"], "id_sp": s["id_sp"], "section_id": sid,
                "span_ids": [str(x) for x in s["span_ids"]], "title": s["title"],
                "section_title": s["section_title"], "text": s["text"], "score": score, **extra}

    # --- A: KG -> sections ----------------------------------------------------------------

    def rank_sections(self, linked: List[Dict[str, Any]], expand: bool = False, k: int = POOL_K) -> List[Dict[str, Any]]:
        w = self.weights(linked, expand)
        score: Dict[str, float] = defaultdict(float)
        count: Dict[str, int] = defaultdict(int)
        for eid, weight in w.items():
            for sid in self.entities[eid]["section_ids"]:
                if sid in self.sections:
                    score[sid] += weight
                    count[sid] += 1
        ranked = sorted(score, key=lambda sid: (-score[sid], -count[sid], sid))[:k]
        return [self.section_result(sid, rank, score[sid], n_entities=count[sid])
                for rank, sid in enumerate(ranked, start=1)]

    # --- B: KG facts ----------------------------------------------------------------------

    def fact_text(self, r: Dict[str, Any]) -> str:
        a, b = self.entities[r["source"]], self.entities[r["target"]]
        return f"{a['name']} {relation_words(r['relation'])} {b['name']}"

    @property
    def fact_emb(self) -> np.ndarray:
        if self._fact_emb is None:
            path = OUT_DIR / f"facts_{self._scope}_{MODEL_NAME.replace('/', '_')}.npy"
            if path.exists() and np.load(path, mmap_mode="r").shape[0] == len(self.relations):
                self._fact_emb = np.load(path)
            else:
                texts = [self.fact_text(r) + (f": {r['evidence'][0]['text']}" if r["evidence"] else "")
                         for r in self.relations]
                self._fact_emb = self.linker.model.encode(texts, batch_size=256, normalize_embeddings=True,
                                                          convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
                np.save(path, self._fact_emb)
        return self._fact_emb

    def rank_facts(self, linked: List[Dict[str, Any]], query_emb: np.ndarray, budget: int = FACT_BUDGET) -> List[Dict[str, Any]]:
        w = self.weights(linked)
        cand = sorted({i for eid in w for i in self.adjacent[eid]})
        if not cand:
            return []
        by_link = sorted(cand, key=lambda i: (-max(w.get(self.relations[i]["source"], 0.0),
                                                   w.get(self.relations[i]["target"], 0.0)),
                                              -self.relations[i]["support"], i))
        sims = self.fact_emb[cand] @ query_emb
        by_sim = [cand[j] for j in np.argsort(-sims, kind="stable")]
        fused: Dict[int, float] = defaultdict(float)
        for ranking in (by_link, by_sim):
            for rank, i in enumerate(ranking, start=1):
                fused[i] += 1.0 / (RRF_K + rank)
        top = sorted(fused, key=lambda i: (-fused[i], i))[:budget]
        return [{"rank": rank, "relation_index": i, "score": fused[i], **self.relations[i]}
                for rank, i in enumerate(top, start=1)]

    def format_facts(self, facts: List[Dict[str, Any]]) -> str:
        lines = []
        for f in facts:
            a, b = self.entities[f["source"]], self.entities[f["target"]]

            def label(e):
                v = f"; {e['value']}" if e.get("value") and e["value"].casefold() != e["name"].casefold() else ""
                return f"{e['name']} ({e['type']}{v})"
            line = f"[{f['rank']}] {label(a)} {relation_words(f['relation'])} {label(b)}"
            if f["evidence"]:
                ev = f["evidence"][0]
                s = self.sections.get(ev["section_id"])
                src = f" ({s['title']}{' — ' + s['section_title'] if s and s.get('section_title') else ''})" if s else ""
                line += f'\n    Evidence: "{ev["text"]}"{src}'
            lines.append(line)
        return "\n".join(lines)

    def fact_sections(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sections behind the facts, in fact order (first evidence section, else first section)."""
        seen, out = set(), []
        for f in facts:
            sid = f["evidence"][0]["section_id"] if f["evidence"] else (f["section_ids"] or [None])[0]
            if sid and sid in self.sections and sid not in seen:
                seen.add(sid)
                out.append(self.section_result(sid, len(out) + 1, f["score"]))
        return out


def rrf_sections(rankings: List[List[Dict[str, Any]]], k: int = POOL_K) -> List[Dict[str, Any]]:
    scores: Dict[str, float] = defaultdict(float)
    first: Dict[str, Dict[str, Any]] = {}
    for ranking in rankings:
        for r in ranking:
            scores[r["section_id"]] += 1.0 / (RRF_K + r["rank"])
            first.setdefault(r["section_id"], r)
    ranked = sorted(scores, key=lambda sid: (-scores[sid], sid))[:k]
    return [{**first[sid], "rank": rank, "rrf_score": scores[sid]} for rank, sid in enumerate(ranked, start=1)]
