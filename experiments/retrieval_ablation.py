"""Retrieval-only ablations on dev-500 (no LLM calls): stronger embedding models and fusion of
the reranker score with the first-stage ranking.

For each dense model the pipeline is the Step 4 one: rewritten query, BM25 + dense fused by
RRF (top-50), then the bge-reranker-base cross-encoder. Each variant is scored by section
Recall@1/5/10 and the recall of the 50 candidates, with a paired bootstrap on Recall@5
against the current pipeline (bge-small, reranker only).

Fusion of the final ranking: the reranker order alone (current), RRF of the reranker and
first-stage ranks, or a weighted sum of min-max normalised scores.

    python experiments/retrieval_ablation.py
    python experiments/retrieval_ablation.py --models BAAI/bge-small-en-v1.5 BAAI/bge-base-en-v1.5
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import paired_bootstrap_test
from experiments.run_dev_subset import RERANKER_CACHE_DIR, recall_at_k
from src.data.loader import load_sections
from src.kg_rag.queries import load_step4
from src.rag.retriever import BM25Retriever, _tokenize

OUT_DIR = PROJECT_ROOT / "experiments" / "results" / "dev_500"
EMB_DIR = PROJECT_ROOT / "data" / "cache"
POOL = 50
RRF_K = 60
MODELS = {
    # name: (query prefix, passage prefix)
    "BAAI/bge-small-en-v1.5": ("Represent this sentence for searching relevant passages: ", ""),
    "BAAI/bge-base-en-v1.5": ("Represent this sentence for searching relevant passages: ", ""),
    "BAAI/bge-large-en-v1.5": ("Represent this sentence for searching relevant passages: ", ""),
    "intfloat/e5-large-v2": ("query: ", "passage: "),
}
WEIGHTS = (0.3, 0.5, 0.7)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def section_embeddings(model, name: str, texts: List[str]) -> np.ndarray:
    path = EMB_DIR / f"dense_embeddings_{name.replace('/', '_')}_sections.npy"
    if path.exists():
        emb = np.load(path)
        if emb.shape[0] == len(texts):
            return emb
    prefix = MODELS[name][1]
    emb = model.encode([prefix + t for t in texts], batch_size=32, normalize_embeddings=True,
                       convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
    np.save(path, emb)
    return emb


def rrf(rankings: List[List[int]], k: int = RRF_K) -> Dict[int, float]:
    scores: Dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return scores


def minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = float(x.min()), float(x.max())
    return np.zeros_like(x) if hi == lo else (x - lo) / (hi - lo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    args = parser.parse_args()

    step4 = load_step4("dev500")
    examples, records = step4["examples"], step4["records"]
    queries = [records[ex["example_id"]]["rewritten"] for ex in examples]
    sections = load_sections()
    texts = [s["text"] for s in sections]
    as_result = lambda i, rank: {"rank": rank, "doc_id": sections[i]["doc_id"], "id_sp": sections[i]["id_sp"],
                                 "span_ids": [str(x) for x in sections[i]["span_ids"]]}

    bm25 = BM25Retriever()
    bm25.corpus_size
    bm25_rank = []
    for q in queries:
        sc = bm25._bm25.get_scores(_tokenize(q))
        bm25_rank.append(list(np.argsort(-sc, kind="stable")[:POOL * 3]))

    from sentence_transformers import SentenceTransformer
    from src.rag.reranker import Reranker
    reranker = Reranker(cache_dir=RERANKER_CACHE_DIR)

    rows: Dict[str, List[Dict[str, float]]] = {}
    summary: Dict[str, Any] = {"examples": len(examples), "pool": POOL, "variants": {}}
    for name in args.models:
        log(f"model {name}")
        model = SentenceTransformer(name)
        emb = section_embeddings(model, name, texts)
        q_emb = model.encode([MODELS[name][0] + q for q in queries], batch_size=64, normalize_embeddings=True,
                             convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
        del model
        dense_scores = q_emb @ emb.T
        dense_rank = [list(np.argsort(-s)[:POOL * 3]) for s in dense_scores]

        candidates, first_stage = [], []
        for b, d in zip(bm25_rank, dense_rank):
            fused = rrf([b, d])
            top = sorted(fused, key=lambda i: -fused[i])[:POOL]
            candidates.append(top)
            first_stage.append({i: fused[i] for i in top})

        log(f"  reranking {len(queries)} x {POOL}")
        cand_dicts = [[{"text": texts[i], "idx": i} for i in top] for top in candidates]
        ranked = reranker.rerank_many(queries, cand_dicts, top_k=POOL)
        rr_scores = [{c["idx"]: c["reranker_score"] for c in docs} for docs, _ in ranked]

        short = name.split("/")[-1]
        variants = {
            f"{short}, dense only": [[i for i in dr[:POOL]] for dr in dense_rank],
            f"{short}, hybrid, no reranker": candidates,
            f"{short}, hybrid + reranker": [sorted(c, key=lambda i: -rs[i]) for c, rs in zip(candidates, rr_scores)],
            f"{short}, RRF(reranker, hybrid)": [],
        }
        for c, rs, fs in zip(candidates, rr_scores, first_stage):
            rr_rank = sorted(c, key=lambda i: -rs[i])
            f = rrf([rr_rank, c])
            variants[f"{short}, RRF(reranker, hybrid)"].append(sorted(c, key=lambda i: -f[i]))
        for w in WEIGHTS:
            key = f"{short}, {w:.1f} reranker + {1 - w:.1f} hybrid"
            variants[key] = []
            for c, rs, fs in zip(candidates, rr_scores, first_stage):
                r = minmax(np.array([rs[i] for i in c])); h = minmax(np.array([fs[i] for i in c]))
                s = w * r + (1 - w) * h
                variants[key].append([c[j] for j in np.argsort(-s, kind="stable")])

        for vname, ranks in variants.items():
            per = []
            for ex, ranking in zip(examples, ranks):
                res = [as_result(i, k) for k, i in enumerate(ranking, start=1)]
                per.append({k: recall_at_k(res, ex["grounding"], k) for k in (1, 5, 10, POOL)})
            rows[vname] = per
            summary["variants"][vname] = {f"R@{k}": float(np.mean([p[k] for p in per])) for k in (1, 5, 10, POOL)}
            s = summary["variants"][vname]
            log(f"  {vname:45} R@1 {s['R@1']:.1%}  R@5 {s['R@5']:.1%}  R@10 {s['R@10']:.1%}  R@50 {s['R@50']:.1%}")

    base = "bge-small-en-v1.5, hybrid + reranker"
    if base in rows:
        for vname, per in rows.items():
            if vname != base:
                t = paired_bootstrap_test([p[5] for p in per], [p[5] for p in rows[base]])
                summary["variants"][vname]["dR@5_vs_current"] = t
    (OUT_DIR / "retrieval_ablation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# Retrieval ablation (dev-500, no LLM calls)", "",
             "Section recall; ΔR@5 is the paired bootstrap difference to the current pipeline (bge-small, hybrid + reranker).", "",
             "| Variant | R@1 | R@5 | R@10 | R@50 | ΔR@5 [95% CI] |", "| :--- | :---: | :---: | :---: | :---: | :---: |"]
    for vname, s in summary["variants"].items():
        t = s.get("dR@5_vs_current")
        d = f"{t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]" if t else "-"
        lines.append(f"| {vname} | {s['R@1']*100:.1f} | {s['R@5']*100:.1f} | {s['R@10']*100:.1f} | {s['R@50']*100:.1f} | {d} |")
    (OUT_DIR / "retrieval_ablation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"done -> {OUT_DIR / 'retrieval_ablation.md'}")


if __name__ == "__main__":
    main()
