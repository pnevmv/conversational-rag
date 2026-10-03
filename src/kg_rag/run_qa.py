"""Phase 2: KG retrievers and QA on dev-500, comparable with Step 4.

Pipelines (output experiments/results/dev_500/<name>.jsonl, Step 4 record schema):
  kg_sections         A: KG -> sections, top-5 as context
  kg_sections_1hop    A with 1-hop expansion through entity relations
  kg_facts            B: top-30 KG facts with evidence quotes as context (no raw sections)
  kg_hybrid           C: RRF(A, Step 4 best) -> cross-encoder rerank -> top-5
  kg_rerank           D: A's top-50 reranked by the Step 4 cross-encoder (KG as candidate generator)
  step4_plus_facts    E: the Step 4 best top-5 sections, followed by B's KG facts in a separate
                      "Facts" block
  step4_plus_random_facts  E-random (control): the Step 4 top-5 sections plus as many KG facts as E,
                      drawn at random (fixed seed) from the facts of the example's domain

All use the rewritten query for linking (top-10 entities, hubs kept); A, B, D and E link
without the domain filter (the predicted domain comes from Step 4 retrieval), C with it. The
generator, agent-style prompt and model are those of Step 4 (rag_rewrite_rerank_v2), and
the question in the prompt is the raw user turn, as in Step 4.

Usage:
    python -m src.kg_rag.run_qa --retrieval-only     # recall only, no generation
    python -m src.kg_rag.run_qa --workers 12
"""
import argparse
import json
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from experiments.run_dev_subset import (RESULTS_DIR, _build_agent_prompt, _load_few_shot_examples,
                                        domain_recall_at_k, format_context, recall_at_k, write_jsonl)
from src.data.loader import load_doc_domain_map
from src.kg_rag.linker import EntityLinker
from src.kg_rag.queries import DOMAIN_CONFIDENCE, LLM_CACHE_DIR, OUT_DIR, RERANKER_CACHE_DIR, load_step4
from src.kg_rag.retrievers import KGRetriever, rrf_sections
from src.llm import LLMCache, LLMClient, generate_batch

TOP_K = 5
PIPELINES = ("kg_sections", "kg_sections_1hop", "kg_facts", "kg_hybrid", "kg_rerank", "step4_plus_facts",
             "step4_plus_random_facts")
RANDOM_SEED = 42


def facts_by_domain(kg: KGRetriever) -> Dict[str, List[int]]:
    """Relation indices per domain (domain of the document of its first evidence section)."""
    ddm = load_doc_domain_map()
    out: Dict[str, List[int]] = defaultdict(list)
    for i, r in enumerate(kg.relations):
        sid = r["evidence"][0]["section_id"] if r["evidence"] else (r["section_ids"] or [None])[0]
        dom = ddm.get(kg.sections[sid]["doc_id"]) if sid in kg.sections else None
        if dom:
            out[dom].append(i)
    return out


def random_facts(kg: KGRetriever, pool: List[int], n: int, example_id: str) -> List[Dict[str, Any]]:
    rng = random.Random(f"{RANDOM_SEED}:{example_id}")
    picked = rng.sample(pool, min(n, len(pool)))
    return [{"rank": rank, "relation_index": i, "score": 0.0, **kg.relations[i]}
            for rank, i in enumerate(picked, start=1)]


def retrieve_all(hybrid_base: str = "kg_sections") -> Dict[str, Any]:
    step4 = load_step4()
    examples, records = step4["examples"], step4["records"]
    linker = EntityLinker("full")
    kg = KGRetriever(linker)
    _ = kg.fact_emb

    queries = [records[ex["example_id"]]["rewritten"] for ex in examples]
    t = time.time()
    embs = linker.encode(queries)
    encode_ms = (time.time() - t) / len(queries) * 1000

    pools = facts_by_domain(kg)
    out: Dict[str, List[Dict[str, Any]]] = {p: [] for p in PIPELINES}
    ms: Dict[str, List[float]] = {p: [] for p in PIPELINES}
    for ex, q, emb in zip(examples, queries, embs):
        rec = records[ex["example_id"]]
        t = time.time()
        linked = kg.link(q, emb)
        link_ms = (time.time() - t) * 1000
        for name, expand in (("kg_sections", False), ("kg_sections_1hop", True)):
            t = time.time()
            ranking = kg.rank_sections(linked, expand=expand)
            ms[name].append(link_ms + (time.time() - t) * 1000)
            out[name].append({"linked": linked, "ranking": ranking})

        t = time.time()
        facts = kg.rank_facts(linked, emb)
        ms["kg_facts"].append(link_ms + (time.time() - t) * 1000)
        out["kg_facts"].append({"linked": linked, "facts": facts, "ranking": kg.fact_sections(facts)})

        # D: A's candidates (no domain filter), reranked below.
        out["kg_rerank"].append({"linked": linked, "candidates": out["kg_sections"][-1]["ranking"]})
        ms["kg_rerank"].append(ms["kg_sections"][-1])

        # E: Step 4 sections, plus B's facts.
        step4_top5 = [kg.section_result(r["section_id"], r["rank"], r["reranker_score"])
                      for r in rec["step4_ranking"][:TOP_K]]
        out["step4_plus_facts"].append({"linked": linked, "facts": facts, "ranking": step4_top5})
        ms["step4_plus_facts"].append(ms["kg_facts"][-1])

        # E-random: same sections, same number of facts, drawn at random from the domain.
        rnd = random_facts(kg, pools[ex["domain"]], len(facts), ex["example_id"])
        out["step4_plus_random_facts"].append({"linked": linked, "facts": rnd, "ranking": step4_top5})
        ms["step4_plus_random_facts"].append(0.0)

        # C: domain filter allowed; A's ranking re-linked with the predicted domain.
        t = time.time()
        dom = rec["pred_domain"] if rec["pred_domain_conf"] >= DOMAIN_CONFIDENCE else None
        linked_c = kg.link(q, emb, domain=dom) if dom else linked
        a_rank = kg.rank_sections(linked_c, expand=hybrid_base == "kg_sections_1hop")
        step4_rank = [kg.section_result(r["section_id"], r["rank"], r["reranker_score"]) for r in rec["step4_ranking"]
                      if r["section_id"] in kg.sections]
        fused = rrf_sections([a_rank, step4_rank])
        ms["kg_hybrid"].append(link_ms + (time.time() - t) * 1000)
        out["kg_hybrid"].append({"linked": linked_c, "candidates": fused, "a_ranking": a_rank})

    # C: rerank the fused candidates (batched; scores cached on disk like Step 4).
    from src.rag import Reranker
    reranker = Reranker(cache_dir=RERANKER_CACHE_DIR)
    t = time.time()
    reranked = reranker.rerank_many(queries, [o["candidates"] for o in out["kg_hybrid"]], top_k=TOP_K)
    rerank_ms = (time.time() - t) / len(queries) * 1000
    for ex, o, (docs, _) in zip(examples, out["kg_hybrid"], reranked):
        o["ranking"] = docs
        step4_top = {r["section_id"] for r in records[ex["example_id"]]["step4_ranking"][:TOP_K]}
        o["new_vs_step4"] = sum(1 for d in docs if d["section_id"] not in step4_top)

    t = time.time()
    reranked = reranker.rerank_many(queries, [o["candidates"] for o in out["kg_rerank"]], top_k=TOP_K)
    rerank_d_ms = (time.time() - t) / len(queries) * 1000
    for ex, o, (docs, _) in zip(examples, out["kg_rerank"], reranked):
        o["ranking"] = docs
        step4_top = {r["section_id"] for r in records[ex["example_id"]]["step4_ranking"][:TOP_K]}
        o["new_vs_step4"] = sum(1 for d in docs if d["section_id"] not in step4_top)

    return {"step4": step4, "kg": kg, "out": out, "queries": queries,
            "latency_ms": {"encode": encode_ms, **{p: float(np.mean(v)) for p, v in ms.items()},
                           "kg_hybrid_rerank": rerank_ms, "kg_rerank_rerank": rerank_d_ms}}


def build_records(name: str, examples, queries, results, kg: KGRetriever, ddm, template: str):
    rows, prompts = [], []
    for ex, q, res in zip(examples, queries, results):
        ranking = res["ranking"]
        if name == "kg_facts":
            context = kg.format_facts(res["facts"])
        elif name in ("step4_plus_facts", "step4_plus_random_facts"):
            context = format_context(ranking[:TOP_K]) + "\n\nFacts:\n" + kg.format_facts(res["facts"])
        else:
            context = format_context(ranking[:TOP_K])
        prompts.append(template.format(context=context, question=ex["question"]))
        rows.append({
            "example_id": ex["example_id"], "domain": ex["domain"], "dialogue_id": ex["dialogue_id"],
            "turn_id": ex["turn_id"], "question": ex["question"], "reference_answer": ex["reference_answer"],
            "is_unanswerable": ex.get("is_unanswerable", False), "is_doc_switch": ex.get("is_doc_switch", False),
            "document_id": ex["document_id"], "grounding": ex["grounding"], "context": context,
            "rewritten_query": q,
            "recall_at_1": recall_at_k(ranking, ex["grounding"], 1),
            "recall_at_5": recall_at_k(ranking, ex["grounding"], 5),
            "domain_recall": domain_recall_at_k(ranking, ex["domain"], TOP_K, ddm),
            "linked_entities": [{"entity_id": l["entity_id"], "name": l["name"], "type": l["type"],
                                 "degree": l["degree"]} for l in res["linked"]],
            "retrieved_sections": [r["section_id"] for r in ranking[:TOP_K]],
        })
        if name in ("kg_hybrid", "kg_rerank"):
            rows[-1]["new_vs_step4"] = res["new_vs_step4"]
        if name in ("kg_facts", "step4_plus_facts", "step4_plus_random_facts"):
            fact_secs = kg.fact_sections(res["facts"])
            rows[-1]["n_facts"] = len(res["facts"])
            rows[-1]["facts_context_recall"] = recall_at_k(fact_secs, ex["grounding"], len(fact_secs) or 1)
        if name == "kg_facts":
            rows[-1]["n_facts"] = len(res["facts"])
            rows[-1]["context_recall"] = recall_at_k(ranking, ex["grounding"], len(ranking) or 1)
    return rows, prompts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--hybrid-base", choices=["kg_sections", "kg_sections_1hop"], default="kg_sections")
    args = parser.parse_args()

    t0 = time.time()
    data = retrieve_all(args.hybrid_base)
    step4, kg, out, queries = data["step4"], data["kg"], data["out"], data["queries"]
    examples = step4["examples"]
    ddm = load_doc_domain_map()
    template = _build_agent_prompt(_load_few_shot_examples())

    summary: Dict[str, Any] = {"latency_ms": data["latency_ms"], "hybrid_base": args.hybrid_base, "pipelines": {}}
    all_rows = {}
    for name in PIPELINES:
        rows, prompts = build_records(name, examples, queries, out[name], kg, ddm, template)
        all_rows[name] = (rows, prompts)
        if name in ("step4_plus_facts", "step4_plus_random_facts"):
            # The sections part must be exactly the Step 4 context.
            base = {json.loads(l)["example_id"]: json.loads(l)["context"]
                    for l in open(RESULTS_DIR / "rag_rewrite_rerank_v2.jsonl", encoding="utf-8")}
            bad = sum(1 for r in rows if not r["context"].startswith(base[r["example_id"]] + "\n\nFacts:\n"))
            assert bad == 0, f"{bad} contexts differ from the Step 4 context"
        s = {"recall_at_1": float(np.mean([r["recall_at_1"] for r in rows])),
             "recall_at_5": float(np.mean([r["recall_at_5"] for r in rows])),
             "domain_recall": float(np.mean([r["domain_recall"] for r in rows])),
             "prompt_chars": float(np.mean([len(p) for p in prompts]))}
        if name == "kg_facts":
            s["context_recall"] = float(np.mean([r["context_recall"] for r in rows]))
            s["empty_context"] = sum(1 for r in rows if r["n_facts"] == 0)
            s["mean_facts"] = float(np.mean([r["n_facts"] for r in rows]))
        summary["pipelines"][name] = s
        print(f"{name:18} R@1 {s['recall_at_1']:.1%}  R@5 {s['recall_at_5']:.1%}  domain {s['domain_recall']:.1%}  "
              f"prompt {s['prompt_chars']:.0f} chars" + (f"  context recall {s['context_recall']:.1%}, "
                                                         f"{s['empty_context']} empty" if name == "kg_facts" else ""))
    print(f"latency (ms/question): {data['latency_ms']}")
    if args.retrieval_only:
        return

    cache = LLMCache(LLM_CACHE_DIR)
    client = LLMClient()
    for name in PIPELINES:
        rows, prompts = all_rows[name]
        print(f"=== {name}: generating {len(prompts)} answers ===")
        answers = generate_batch(client, prompts, cache=cache, max_workers=args.workers, verbose=False)
        for row, prompt, (answer, status) in zip(rows, prompts, answers):
            row.update({"prompt": prompt, "model_answer": answer,
                        "status": status if answer is not None else "error",
                        "error": None if answer is not None else status})
        n_err = sum(1 for r in rows if r["status"] == "error")
        write_jsonl(rows, RESULTS_DIR / f"{name}.jsonl")
        print(f"  {n_err} errors -> {RESULTS_DIR / f'{name}.jsonl'}")
    summary["llm"] = {"rewrite_calls_per_question": step4["rewrite_stats"]["llm_calls"] / len(examples),
                      "generation_calls_per_question": 1.0, "cache": cache.stats}
    summary["wall_time_s"] = time.time() - t0
    (OUT_DIR / "phase2_retrieval.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"cache: {cache.stats}; wall time {summary['wall_time_s']:.0f}s")


if __name__ == "__main__":
    main()
