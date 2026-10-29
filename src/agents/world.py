"""Retrieval world of the Step 8 agents: the context of E for a question, and the two ways of looking further
(a new passage search, more graph facts), over the existing modules.

The context of E is rebuilt exactly as in the final system (Step 4 top 5 + up to 30 facts of the 10 linked
entities); `render` gives its text, with the facts labelled [F1], [F2], ... when cite is true.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

from experiments.run_dev_subset import format_context
from src.data.loader import make_section_id
from src.kg_rag.linker import EntityLinker
from src.kg_rag.queries import RERANKER_CACHE_DIR, RETRIEVE_K, TOP_K, load_step4
from src.kg_rag.retrievers import KGRetriever

NEW_FACTS = 15


@dataclass
class Turn:
    """Context state of one question: sections numbered 1.., facts numbered 1.. (shown as [F<n>] when cited)."""
    example: Dict[str, Any]
    query: str
    emb: np.ndarray
    gold: Set[str]
    linked: List[Dict[str, Any]]
    sections: List[Dict[str, Any]]
    facts: List[Dict[str, Any]]
    log: List[Dict[str, Any]] = field(default_factory=list)

    def section_ids(self) -> List[str]:
        return [s["section_id"] for s in self.sections]

    def fact_relations(self) -> Set[int]:
        return {f["relation_index"] for f in self.facts}


class World:
    def __init__(self, split: str):
        self.split = split
        step4 = load_step4(split)
        self.examples = {ex["example_id"]: ex for ex in step4["examples"]}
        self.records = step4["records"]
        self.linker = EntityLinker("full")
        self.kg = KGRetriever(self.linker)
        _ = self.kg.fact_emb
        self._retriever = None
        self._reranker = None

    # ------------------------------------------------------------------ the context of E
    def turns(self, ids: List[str]) -> Dict[str, Turn]:
        queries = [self.records[i]["rewritten"] for i in ids]
        embs = self.linker.encode(queries)
        out = {}
        for i, q, emb in zip(ids, queries, embs):
            rec = self.records[i]
            linked = self.kg.link(q, emb)
            sections = [self.kg.section_result(r["section_id"], r["rank"], r["reranker_score"])
                        for r in rec["step4_ranking"][:TOP_K]]
            out[i] = Turn(self.examples[i], q, emb, set(rec["gold_sections"]), linked, sections,
                          self.kg.rank_facts(linked, emb))
        return out

    def render(self, sections: List[Dict[str, Any]], facts: List[Dict[str, Any]], cite: bool = False) -> str:
        text = format_context(sections)
        if facts:
            block = self.kg.format_facts(facts)
            if cite:
                block = re.sub(r"^\[(\d+)\] ", r"[F\1] ", block, flags=re.M)
            text += "\n\nFacts:\n" + block
        return text

    def fact_section_ids(self, facts: List[Dict[str, Any]]) -> Set[str]:
        return {s["section_id"] for s in self.kg.fact_sections(facts)}

    def gold_in_context(self, t: Turn, sections: Optional[List[Dict[str, Any]]] = None,
                        facts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, bool]:
        """Strict: a gold section among the passages. Broad: or the evidence section of a fact."""
        sections = t.sections if sections is None else sections
        facts = t.facts if facts is None else facts
        strict = bool(t.gold & {s["section_id"] for s in sections})
        return {"strict": strict, "broad": strict or bool(t.gold & self.fact_section_ids(facts))}

    # ------------------------------------------------------------------ looking further
    def search(self, queries: List[str]) -> List[List[Dict[str, Any]]]:
        """Step 4 retrieval for new queries: hybrid top 50, reranked; returns the full reranked lists."""
        from src.rag import HybridRetriever, Reranker
        if self._retriever is None:
            self._retriever = HybridRetriever()
            self._retriever.build_index()
            self._reranker = Reranker(cache_dir=RERANKER_CACHE_DIR)
        cands = [self._retriever.retrieve(q, top_k=RETRIEVE_K) for q in queries]
        ranked = self._reranker.rerank_many(queries, cands, top_k=RETRIEVE_K)
        out = []
        for docs, _ in ranked:
            out.append([self.kg.section_result(make_section_id(d["doc_id"], d["id_sp"]), n, d["reranker_score"])
                        for n, d in enumerate(docs, start=1)])
        return out

    def add_sections(self, t: Turn, ranked: List[Dict[str, Any]], k: int = TOP_K) -> List[Dict[str, Any]]:
        """Sections of the top k of a new ranking that are not in the context yet, numbered on."""
        have = set(t.section_ids())
        new = [s for s in ranked[:k] if s["section_id"] not in have]
        return [{**s, "rank": len(t.sections) + n} for n, s in enumerate(new, start=1)]

    def add_facts(self, t: Turn, linked: List[Dict[str, Any]], emb: np.ndarray, n: int = NEW_FACTS) -> List[Dict[str, Any]]:
        """Facts of the given entities ranked as in E against emb, without the ones already in the context."""
        have = t.fact_relations()
        cand = [f for f in self.kg.rank_facts(linked, emb, budget=10 * n) if f["relation_index"] not in have][:n]
        return [{**f, "rank": len(t.facts) + k} for k, f in enumerate(cand, start=1)]

    def new_entities(self, t: Turn, linked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        known = {l["entity_id"] for l in t.linked}
        return [l for l in linked if l["entity_id"] not in known]
