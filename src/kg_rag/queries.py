"""Queries and the Step 4 best retrieval (hybrid + rewrite + rerank) for one split, cached in
experiments/kg_rag/step4_<split>.json (split: dev500, validation or test).

The predicted domain is the majority domain of the Step 4 top-5 (there is no domain
classifier in Step 4).
"""
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.data.loader import load_doc_domain_map, load_qa_pairs, load_sections, make_section_id
from src.kg.coverage import load_examples
from src.llm import LLMCache, LLMClient, generate_batch
from src.rag.query_rewriter import REWRITE_PROMPT, _format_history

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "experiments" / "kg_rag"
LLM_CACHE_DIR = PROJECT_ROOT / "experiments" / "cache"
RERANKER_CACHE_DIR = LLM_CACHE_DIR / "reranker"
SPLITS = ("dev500", "validation", "test")
RETRIEVE_K = 50
TOP_K = 5
DOMAIN_CONFIDENCE = 0.8  # 4 of the top-5 sections in one domain


def split_examples(split: str) -> List[Dict[str, Any]]:
    if split == "test":
        return load_qa_pairs(split="test", max_examples=None)
    return load_examples("dev500" if split == "dev500" else "validation")


def step4_cache(split: str) -> Path:
    return OUT_DIR / f"step4_{split}.json"


def last_agent_turn(example: Dict[str, Any]) -> Optional[str]:
    for turn in reversed(example.get("dialogue_history") or []):
        if turn["role"] == "agent":
            return turn["utterance"].strip()
    return None


def section_of_span() -> Dict[Tuple[str, str], str]:
    return {(s["doc_id"], str(sp)): make_section_id(s["doc_id"], s["id_sp"])
            for s in load_sections() for sp in s["span_ids"]}


def gold_section_ids(example: Dict[str, Any], span_map: Dict[Tuple[str, str], str]) -> List[str]:
    return sorted({span_map[(g["doc_id"], str(g["id_sp"]))] for g in example.get("grounding") or []
                   if (g.get("doc_id"), str(g.get("id_sp"))) in span_map})


def rewrite_all(examples: List[Dict[str, Any]], client: Optional[LLMClient] = None,
                workers: int = 8) -> Tuple[List[str], Dict[str, int]]:
    """Step 4 rewrites (cached). First turns keep the raw question. Returns (queries, call stats)."""
    cache = LLMCache(LLM_CACHE_DIR)
    client = client or LLMClient()
    prompts = {i: REWRITE_PROMPT.format(history=_format_history(ex["dialogue_history"]), question=ex["question"])
               for i, ex in enumerate(examples) if ex.get("dialogue_history")}
    idx = sorted(prompts)
    print(f"  rewriting {len(idx)} turns", flush=True)
    answers = generate_batch(client, [prompts[i] for i in idx], cache=cache, max_workers=workers, verbose=len(idx) > 1000)
    out = [ex["question"] for ex in examples]
    for i, (answer, _) in zip(idx, answers):
        if answer and answer.strip():
            out[i] = answer.strip()
    return out, {"llm_calls": len(idx), "cache_hits": cache.stats["hits"]}


def predict_domain(top: List[Dict[str, Any]], doc_domain: Dict[str, str]) -> Tuple[Optional[str], float]:
    doms = [doc_domain.get(r["doc_id"]) for r in top[:TOP_K]]
    doms = [d for d in doms if d]
    if not doms:
        return None, 0.0
    dom, n = Counter(doms).most_common(1)[0]
    return dom, n / len(doms)


def _step4_retrieval(rewritten: List[str]) -> List[List[Dict[str, Any]]]:
    from src.rag import HybridRetriever, Reranker

    retriever = HybridRetriever()
    retriever.build_index()
    candidates = []
    for i, q in enumerate(rewritten, 1):
        candidates.append(retriever.retrieve(q, top_k=RETRIEVE_K))
        if i % 1000 == 0:
            print(f"  hybrid retrieval {i}/{len(rewritten)}", flush=True)
    print(f"  reranking {len(rewritten)} x {RETRIEVE_K} candidates", flush=True)
    reranker = Reranker(cache_dir=RERANKER_CACHE_DIR)
    ranked = reranker.rerank_many(rewritten, candidates, top_k=RETRIEVE_K)
    out = []
    for docs, _ in ranked:
        out.append([{"rank": d["rank"], "doc_id": d["doc_id"], "id_sp": str(d["id_sp"]),
                     "section_id": make_section_id(d["doc_id"], d["id_sp"]),
                     "span_ids": [str(s) for s in d.get("span_ids", [d["id_sp"]])],
                     "reranker_score": d["reranker_score"]} for d in docs])
    return out


def load_step4(split: str = "dev500", workers: int = 8, refresh: bool = False) -> Dict[str, Any]:
    """{"examples": [...in split order...], "records": {example_id: {...}}, "rewrite_stats": {...}}."""
    examples = split_examples(split)
    cache_file = step4_cache(split)
    if cache_file.exists() and not refresh:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return {"examples": examples, **data}

    rewritten, stats = rewrite_all(examples, workers=workers)
    retrieval = _step4_retrieval(rewritten)
    doc_domain = load_doc_domain_map()
    span_map = section_of_span()
    records = {}
    for ex, rw, top in zip(examples, rewritten, retrieval):
        dom, conf = predict_domain(top, doc_domain)
        records[ex["example_id"]] = {
            "raw": ex["question"], "rewritten": rw, "last_agent": last_agent_turn(ex),
            "gold_sections": gold_section_ids(ex, span_map),
            "pred_domain": dom, "pred_domain_conf": conf, "step4_ranking": top,
        }
    data = {"records": records, "rewrite_stats": stats}
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return {"examples": examples, **data}
