"""Step 7, Graph RAG variants on the validation split (plans/step7-graph-rag.md).

Every variant uses gpt-5.4-nano with G2 + abstain(G0): G0 (current user turn) on every
question, G2 (whole gold dialogue history) when G0 does not abstain; on first turns the two
prompts are the same. Rewrites, passages and linked entities come from the cache.

    V0   graph facts only (B) with dialogue history
    V1   passages + the top-k one-hop facts by cross-encoder score (k = 5, 10), facts below a
         score threshold dropped (threshold chosen on dev-500), with a random-facts control
    V2   as V1 with k = 10, but the slots are filled first with facts whose evidence section is not
         among the top 5 passages: (a) all 10 slots, (b) 5 out-of-context + 5 in-context

    python experiments/graph_rag.py v0
    python experiments/graph_rag.py score          # cross-encoder score of every candidate fact
    python experiments/graph_rag.py v1-dev         # threshold per k on dev-500
    python experiments/graph_rag.py v1             # full validation, chosen thresholds + controls
    python experiments/graph_rag.py v2
    python experiments/graph_rag.py report
"""
import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import paired_bootstrap_test
from experiments.generator_input import TAIL, build_prompt
from experiments.run_dev_subset import _build_agent_prompt, _load_few_shot_examples
from src.data.loader import load_qa_pairs
from src.evaluation.metrics import compute_metrics, is_abstention
from src.kg_rag.queries import RERANKER_CACHE_DIR
from src.llm import LLMCache, LLMClient, call_meta, generate_batch

VAL = PROJECT_ROOT / "experiments" / "results" / "validation"
GEN = VAL / "generator_input"
OUT = VAL / "graph_rag"
CACHE_DIR = PROJECT_ROOT / "experiments" / "cache"
DEV_IDS = PROJECT_ROOT / "data" / "dev_500_ids.json"
ABSTAIN = "Unfortunately, no relevant information is found."
KS = (5, 10)
THRESHOLDS = (0.0, 0.05, 0.2, 0.5)
RANDOM_SEED = 42
WORKERS = 12


def load(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def write_jsonl(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


_TEMPLATE: Optional[str] = None
_EXAMPLES: Optional[Dict[str, Dict[str, Any]]] = None


def template() -> str:
    global _TEMPLATE
    if _TEMPLATE is None:
        _TEMPLATE = _build_agent_prompt(_load_few_shot_examples())
    return _TEMPLATE


def examples() -> Dict[str, Dict[str, Any]]:
    global _EXAMPLES
    if _EXAMPLES is None:
        _EXAMPLES = {ex["example_id"]: ex for ex in load_qa_pairs(split="validation", max_examples=None)}
    return _EXAMPLES


def generate(name: str, contexts: Dict[str, str], rewritten: Dict[str, str]) -> List[Dict[str, Any]]:
    """G2 + abstain(G0) for every question of contexts; writes OUT/<name>.jsonl."""
    exs = examples()
    ids = list(contexts)
    heads = {i: template().format(context=contexts[i], question="\x00").split("\n\nCustomer: \x00")[0] for i in ids}
    g0 = {i: heads[i] + TAIL.format(question=exs[i]["question"]) for i in ids}
    g2 = {i: build_prompt(heads[i], exs[i], rewritten[i], "G2", None) for i in ids}
    cache, client = LLMCache(CACHE_DIR), LLMClient()
    print(f"=== {name}: G0 on {len(ids)} questions", flush=True)
    a0 = dict(zip(ids, generate_batch(client, [g0[i] for i in ids], cache=cache, max_workers=WORKERS,
                                      verbose=len(ids) > 1000, metas=[call_meta(exs[i], "G0", name) for i in ids])))
    need = [i for i in ids if a0[i][0] is not None and not is_abstention(a0[i][0]) and g2[i] != g0[i]]
    print(f"=== {name}: G2 on {len(need)} questions", flush=True)
    a2 = dict(zip(need, generate_batch(client, [g2[i] for i in need], cache=cache, max_workers=WORKERS,
                                       verbose=len(need) > 1000, metas=[call_meta(exs[i], "G2", name) for i in need])))
    rows = []
    for i in ids:
        ans0 = a0[i][0]
        if ans0 is None:
            final, used = None, [g0[i]]
        elif is_abstention(ans0):
            final, used = ABSTAIN, [g0[i]]
        elif i in a2:
            final, used = a2[i][0], [g0[i], g2[i]]
        else:
            final, used = ans0, [g0[i]]
        rows.append({"example_id": i, "dialogue_id": exs[i]["dialogue_id"], "turn_id": exs[i]["turn_id"],
                     "question": exs[i]["question"], "reference_answer": exs[i]["reference_answer"],
                     "is_unanswerable": exs[i]["is_unanswerable"], "context": contexts[i],
                     "prompts": used, "g0_answer": ans0, "model_answer": final})
    write_jsonl(rows, OUT / f"{name}.jsonl")
    print(f"  {sum(r['model_answer'] is None for r in rows)} questions without an answer", flush=True)
    return rows


def rewrites() -> Dict[str, str]:
    return {r["example_id"]: r["rewritten_query"] or r["question"] for r in load(VAL / "step4_plus_facts.jsonl")}


# ---------------------------------------------------------------------------- V0
def run_v0() -> None:
    ctx = {r["example_id"]: r["context"] for r in load(VAL / "kg_facts.jsonl")}
    generate("v0_graph_facts", ctx, rewrites())


# ---------------------------------------------------------------------------- V1
_KG = None


def kg():
    global _KG
    if _KG is None:
        from src.kg_rag.linker import EntityLinker
        from src.kg_rag.retrievers import KGRetriever
        _KG = KGRetriever(EntityLinker("full"))
    return _KG


def fact_text(r: Dict[str, Any]) -> str:
    t = kg().fact_text(r)
    return t + (f": {r['evidence'][0]['text']}" if r["evidence"] else "")


def score_facts() -> None:
    """Cross-encoder score of every one-hop candidate fact against the rewritten query."""
    from src.rag import Reranker
    e_rows = load(VAL / "step4_plus_facts.jsonl")
    g = kg()
    queries, cands, ids = [], [], []
    for r in e_rows:
        rel = sorted({i for l in r["linked_entities"] for i in g.adjacent[l["entity_id"]]})
        ids.append(r["example_id"])
        queries.append(r["rewritten_query"] or r["question"])
        cands.append([{"text": fact_text(g.relations[i]), "relation_index": i} for i in rel])
    print(f"scoring {sum(len(c) for c in cands)} (query, fact) pairs", flush=True)
    ranked = Reranker(cache_dir=RERANKER_CACHE_DIR).rerank_many(queries, cands, top_k=10_000)
    out = {i: [[c["relation_index"], round(float(c["reranker_score"]), 6)] for c in docs]
           for i, (docs, _) in zip(ids, ranked)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fact_scores.json").write_text(json.dumps(out), encoding="utf-8")


def facts_block(rel_ids: List[int]) -> str:
    g = kg()
    facts = [{"rank": k, "relation_index": i, "score": 0.0, **g.relations[i]} for k, i in enumerate(rel_ids, start=1)]
    return g.format_facts(facts)


def v1_contexts(k: int, threshold: float, ids: List[str]) -> Dict[str, str]:
    scores = json.loads((OUT / "fact_scores.json").read_text())
    sections = {r["example_id"]: r["context"].partition("\n\nFacts:\n")[0] for r in load(VAL / "step4_plus_facts.jsonl")}
    out = {}
    for i in ids:
        keep = [rel for rel, s in scores[i][:k] if s >= threshold]
        out[i] = sections[i] + ("\n\nFacts:\n" + facts_block(keep) if keep else "")
    return out


def evidence_section(rel: Dict[str, Any]) -> Optional[str]:
    """Section of a fact's first evidence quote (first section of the fact if it has no quote)."""
    if rel["evidence"]:
        return rel["evidence"][0]["section_id"]
    return (rel["section_ids"] or [None])[0]


def v2_contexts(mode: str, ids: List[str], k: int = 10) -> Dict[str, str]:
    """Top-k facts by cross-encoder score, filling the slots with facts whose evidence section is not
    among the top 5 passages first. mode "a": all k slots out-of-context first; "b": k/2 out-of-context
    and k/2 in-context. A short group is filled from the other, so every question keeps k facts when
    it has them. The kept facts are listed by score, as in V1."""
    scores = json.loads((OUT / "fact_scores.json").read_text())
    e_rows = {r["example_id"]: r for r in load(VAL / "step4_plus_facts.jsonl")}
    g = kg()
    out = {}
    for i in ids:
        top5 = set(e_rows[i]["retrieved_sections"])
        ranked = scores[i]
        outside = [x for x in ranked if evidence_section(g.relations[x[0]]) not in top5]
        inside = [x for x in ranked if evidence_section(g.relations[x[0]]) in top5]
        if mode == "a":
            keep = (outside + inside)[:k]
        else:
            half = k // 2
            keep = outside[:half] + inside[:half]
            rest = [x for x in ranked if x not in keep]
            keep += rest[:k - len(keep)]
        keep = sorted(keep, key=lambda x: -x[1])
        sections = e_rows[i]["context"].partition("\n\nFacts:\n")[0]
        out[i] = sections + ("\n\nFacts:\n" + facts_block([x[0] for x in keep]) if keep else "")
    return out


def run_v2() -> None:
    ids = [r["example_id"] for r in load(VAL / "step4_plus_facts.jsonl")]
    rw = rewrites()
    for mode in ("a", "b"):
        generate(f"v2{mode}_k10", v2_contexts(mode, ids), rw)


def random_contexts(counts: Dict[str, int]) -> Dict[str, str]:
    """Same number of facts per question, drawn at random from the facts of the question's domain."""
    from src.kg_rag.run_qa import facts_by_domain
    pools = facts_by_domain(kg())
    exs = examples()
    sections = {r["example_id"]: r["context"].partition("\n\nFacts:\n")[0] for r in load(VAL / "step4_plus_facts.jsonl")}
    out = {}
    for i, n in counts.items():
        pick = random.Random(f"{RANDOM_SEED}:{i}").sample(pools[exs[i]["domain"]], n) if n else []
        out[i] = sections[i] + ("\n\nFacts:\n" + facts_block(pick) if pick else "")
    return out


def n_facts(ctx: str) -> int:
    return len(re.findall(r"^\[\d+\] ", ctx.partition("\n\nFacts:\n")[2], flags=re.M))


def run_v1_dev() -> None:
    dev = json.loads(DEV_IDS.read_text())
    rw = rewrites()
    res = {}
    for k in KS:
        for t in THRESHOLDS:
            rows = generate(f"v1_dev_k{k}_t{t}", v1_contexts(k, t, dev), rw)
            f = [compute_metrics(r["model_answer"] or "", r["reference_answer"])["f1"] for r in rows]
            res[f"k{k}_t{t}"] = float(np.mean(f))
    best = {}
    for k in KS:
        # best F1; on a tie (within 0.1 point) the higher threshold, i.e. fewer facts
        top = max(res[f"k{k}_t{t}"] for t in THRESHOLDS)
        best[k] = max(t for t in THRESHOLDS if res[f"k{k}_t{t}"] >= top - 0.001)
    (OUT / "v1_dev.json").write_text(json.dumps({"f1": res, "chosen_threshold": best}, indent=2))
    print(json.dumps({"f1": res, "chosen_threshold": best}, indent=2))


def run_v1() -> None:
    chosen = json.loads((OUT / "v1_dev.json").read_text())["chosen_threshold"]
    ids = [r["example_id"] for r in load(VAL / "step4_plus_facts.jsonl")]
    rw = rewrites()
    for k in KS:
        t = chosen[str(k)]
        ctx = v1_contexts(k, t, ids)
        generate(f"v1_k{k}", ctx, rw)
        generate(f"v1_k{k}_random", random_contexts({i: n_facts(c) for i, c in ctx.items()}), rw)


# ---------------------------------------------------------------------------- V3 (retrieval only)
W_GRID = (0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0)


def _minmax(x: Dict[str, float]) -> Dict[str, float]:
    if not x:
        return {}
    lo, hi = min(x.values()), max(x.values())
    return {k: 0.0 if hi == lo else (v - lo) / (hi - lo) for k, v in x.items()}


def run_v3_retrieval() -> None:
    """Rerank the candidate sections with s = ce(section) + w * g(section); R@5 only, no generation."""
    from experiments.run_dev_subset import recall_at_k
    from src.kg_rag.queries import load_step4
    from src.rag import Reranker
    g_ = kg()
    s4 = load_step4("validation")["records"]
    e_rows = {r["example_id"]: r for r in load(VAL / "step4_plus_facts.jsonl")}
    p_rec = {r["example_id"]: r for r in load(VAL / "rag_rewrite_rerank_v2.jsonl")}
    scores = json.loads((OUT / "fact_scores.json").read_text())
    exs = examples()
    ids = list(e_rows)
    queries = {i: e_rows[i]["rewritten_query"] or e_rows[i]["question"] for i in ids}

    # candidate pool: the 50 sections of the passage ranking + evidence sections of the candidate facts
    ce: Dict[str, Dict[str, float]] = {i: {r["section_id"]: r["reranker_score"] for r in s4[i]["step4_ranking"]} for i in ids}
    g_fact: Dict[str, Dict[str, float]] = {}
    new: Dict[str, List[str]] = {}
    for i in ids:
        best: Dict[str, float] = {}
        for rel, sc in scores[i]:
            sid = evidence_section(g_.relations[rel])
            if sid in g_.sections:
                best[sid] = max(best.get(sid, float("-inf")), sc)
        g_fact[i] = best
        new[i] = sorted(sid for sid in best if sid not in ce[i])
    n_new = sum(len(v) for v in new.values())
    print(f"cross-encoder on {n_new} new candidate sections", flush=True)
    ranked = Reranker(cache_dir=RERANKER_CACHE_DIR).rerank_many(
        [queries[i] for i in ids], [[{"text": g_.sections[sid]["text"], "sid": sid} for sid in new[i]] for i in ids],
        top_k=10_000)
    for i, (docs, _) in zip(ids, ranked):
        for d in docs:
            ce[i][d["sid"]] = d["reranker_score"]

    # A's entity-overlap score: summed weights of the linked entities each section mentions
    embs = g_.linker.encode([queries[i] for i in ids])
    g_ent: Dict[str, Dict[str, float]] = {}
    for i, emb in zip(ids, embs):
        w = g_.weights(g_.link(queries[i], emb))
        sc: Dict[str, float] = defaultdict(float)
        for eid, weight in w.items():
            for sid in g_.entities[eid]["section_ids"]:
                sc[sid] += weight
        g_ent[i] = dict(sc)

    def top5(i: str, g: Dict[str, Dict[str, float]], w: float) -> List[str]:
        cn = _minmax(ce[i])
        gn = _minmax({sid: g[i].get(sid, 0.0) for sid in ce[i]})
        return sorted(ce[i], key=lambda sid: (-(cn[sid] + w * gn[sid]), sid))[:5]

    def r5(i: str, sids: List[str]) -> float:
        res = [g_.section_result(sid, k, 0.0) for k, sid in enumerate(sids, start=1)]
        return recall_at_k(res, exs[i]["grounding"], 5)

    dev = set(json.loads(DEV_IDS.read_text()))
    held = [i for i in ids if i not in dev]
    miss_gold = [i for i in ids if p_rec[i]["recall_at_5"] == 0 and e_rows[i]["facts_context_recall"] > 0]
    step4 = {i: r5(i, [r["section_id"] for r in s4[i]["step4_ranking"][:5]]) for i in ids}
    grid = {}
    for gname, g in (("best fact score", g_fact), ("entity overlap", g_ent)):
        for w in W_GRID:
            grid[(gname, w)] = {i: r5(i, top5(i, g, w)) for i in ids}
    base = grid[("best fact score", 0.0)]
    dev_r5 = {k: float(np.mean([v[i] for i in dev])) for k, v in grid.items()}
    best_key = max(dev_r5, key=lambda k: (round(dev_r5[k], 6), -k[1]))
    fmt = lambda t: f"{t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]"
    lines = ["# V3: the graph as a reranker signal (retrieval only, validation)", "",
             "Candidate sections: the 50 of the passage ranking plus the evidence sections of the candidate facts not "
             f"among them ({n_new} new sections in total, {n_new / len(ids):.1f} per question, scored with the same "
             "cross-encoder). Score s = ce + w * g, ce and g min-max normalised per question over the candidate pool; "
             "g = the best cross-encoder score of a candidate fact from that section (V1 scores), or A's entity-overlap "
             "score (summed weights of the linked entities the section mentions). w = 0 is the cross-encoder alone on "
             "the same pool. R@5 in %; Δ is the paired bootstrap difference to w = 0.", "",
             f"Passage ranking as used so far (top 5 of the 50, no new sections): R@5 {np.mean([step4[i] for i in ids])*100:.1f} "
             f"on all, {np.mean([step4[i] for i in held])*100:.1f} held-out, {np.mean([step4[i] for i in miss_gold])*100:.1f} "
             f"on the {len(miss_gold)} 'miss + gold fact' questions.", "",
             "## Dev-500 grid (R@5)", "", "| w | " + " | ".join(str(w) for w in W_GRID) + " |",
             "| :--- |" + " :---: |" * len(W_GRID)]
    for gname in ("best fact score", "entity overlap"):
        lines.append(f"| {gname} | " + " | ".join(f"{dev_r5[(gname, w)]*100:.1f}" for w in W_GRID) + " |")
    lines += ["", "R@5 on the fixed 'miss + gold fact' questions (all validation, diagnostic, not used for tuning):", "",
              "| w | " + " | ".join(str(w) for w in W_GRID) + " |", "| :--- |" + " :---: |" * len(W_GRID)]
    for gname in ("best fact score", "entity overlap"):
        lines.append(f"| {gname} | " + " | ".join(f"{np.mean([grid[(gname, w)][i] for i in miss_gold])*100:.1f}" for w in W_GRID) + " |")
    chosen = grid[best_key]
    lines += ["", f"Chosen on dev-500: g = {best_key[0]}, w = {best_key[1]} (ties go to the smaller w).", "",
              "## Held-out validation and the fixed subset", "",
              "| Ranking | R@5 held-out (n = %d) | Δ vs w = 0 | R@5 'miss + gold fact' (n = %d) | Δ vs w = 0 |" % (len(held), len(miss_gold)),
              "| :--- | :---: | :---: | :---: | :---: |"]
    rows_out = [("passage ranking (top 5 of the 50)", step4), ("w = 0, same pool", base), (f"chosen: {best_key[0]}, w = {best_key[1]}", chosen)]
    for gname in ("best fact score", "entity overlap"):
        k2 = max((k for k in grid if k[0] == gname), key=lambda k: dev_r5[k])
        if k2 != best_key:
            rows_out.append((f"best {gname} on dev-500 (w = {k2[1]})", grid[k2]))
    for name, v in rows_out:
        dh = "-" if v is base else fmt(paired_bootstrap_test([v[i] for i in held], [base[i] for i in held]))
        dm = "-" if v is base else fmt(paired_bootstrap_test([v[i] for i in miss_gold], [base[i] for i in miss_gold]))
        lines.append(f"| {name} | {np.mean([v[i] for i in held])*100:.1f} | {dh} | {np.mean([v[i] for i in miss_gold])*100:.1f} | {dm} |")
    gain = (np.mean([chosen[i] for i in held]) - np.mean([base[i] for i in held])) * 100
    changed = np.mean([len(set(top5(i, g_fact if best_key[0] == "best fact score" else g_ent, best_key[1])) - set(top5(i, g_fact, 0.0))) for i in held])
    lines += ["", f"Held-out R@5 gain of the chosen setting over w = 0: {gain:+.1f} points; on average {changed:.2f} of the 5 "
              f"sections change. Rule of the plan: generation only if this gain is at least 1 point.", ""]
    (OUT / "v3_retrieval.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "v3_retrieval.json").write_text(json.dumps({"chosen": list(best_key), "dev_r5": {f"{k[0]}|{k[1]}": v for k, v in dev_r5.items()},
                                                       "heldout_gain": gain}, indent=2))
    print("\n".join(lines))


# ---------------------------------------------------------------------------- report
_TITLE_TO_SID: Optional[Dict[str, str]] = None


def fact_sections_of(context: str) -> set:
    """Section ids of the evidence quotes in a prompt's Facts block (matched by title and heading)."""
    global _TITLE_TO_SID
    if _TITLE_TO_SID is None:
        g = kg()
        _TITLE_TO_SID = {}
        for sid, sec in g.sections.items():
            label = sec["title"] + (" — " + sec["section_title"] if sec.get("section_title") else "")
            _TITLE_TO_SID.setdefault(label, sid)
    facts = context.partition("\n\nFacts:\n")[2]
    return {_TITLE_TO_SID[t] for t in re.findall(r'^    Evidence: ".*" \((.+)\)$', facts, flags=re.M) if t in _TITLE_TO_SID}


def load_gold() -> Dict[str, set]:
    from src.kg_rag.queries import load_step4
    return {i: set(r["gold_sections"]) for i, r in load_step4("validation")["records"].items()}


def ref_system(base: str) -> List[Dict[str, Any]]:
    """P or E as G2 + abstain(G0), from the cached generator-input answers, in the same format."""
    g0 = load(GEN / f"{base}__G0.jsonl")
    g2 = {r["example_id"]: r for r in load(GEN / f"{base}__G2_kall.jsonl")}
    ctx = {r["example_id"]: r["context"] for r in load(VAL / f"{base}.jsonl")}
    out = []
    for r in g0:
        ab = is_abstention(r["model_answer"] or "")
        two = not ab and g2[r["example_id"]]["prompt"] != r["prompt"]
        out.append({**r, "context": ctx[r["example_id"]], "prompts": [r["prompt"]] + ([g2[r["example_id"]]["prompt"]] if two else []),
                    "g0_answer": r["model_answer"],
                    "model_answer": ABSTAIN if ab else g2[r["example_id"]]["model_answer"]})
    return out


def report() -> None:
    enc = tiktoken.get_encoding("o200k_base")
    ntok = lambda s: len(enc.encode(s or "", disallowed_special=()))
    exs = examples()
    P, E = {r["example_id"]: r for r in ref_system("rag_rewrite_rerank_v2")}, {r["example_id"]: r for r in ref_system("step4_plus_facts")}
    p_rec = {r["example_id"]: r for r in load(VAL / "rag_rewrite_rerank_v2.jsonl")}
    e_rec = {r["example_id"]: r for r in load(VAL / "step4_plus_facts.jsonl")}
    # the two subsets, fixed as defined for E in the graph analysis
    miss_gold = {i for i in E if p_rec[i]["recall_at_5"] == 0 and e_rec[i]["facts_context_recall"] > 0}
    hit_nogold = {i for i in E if p_rec[i]["recall_at_5"] > 0 and e_rec[i]["facts_context_recall"] == 0}
    dev = set(json.loads(DEV_IDS.read_text()))
    held = [i for i in E if i not in dev]
    systems = {"P: passages": P, "E: passages + 30 facts": E}
    for name, label in [("v0_graph_facts", "V0: graph facts only (B)"), ("v1_k5", "V1: top 5 facts"),
                        ("v1_k5_random", "V1 control: 5 random facts"), ("v1_k10", "V1: top 10 facts"),
                        ("v1_k10_random", "V1 control: 10 random facts"),
                        ("v2a_k10", "V2a: 10 facts, out-of-context first"),
                        ("v2b_k10", "V2b: 5 out-of-context + 5 in-context")]:
        path = OUT / f"{name}.jsonl"
        if path.exists():
            systems[label] = {r["example_id"]: r for r in load(path)}
    f1 = lambda r: compute_metrics(r["model_answer"] or "", r["reference_answer"])["f1"]
    fmt = lambda t: f"{t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]"
    tok_in = {lab: float(np.mean([sum(ntok(p) for p in r["prompts"]) for r in s.values()])) for lab, s in systems.items()}
    tok_out = {lab: float(np.mean([ntok(r["g0_answer"]) + (ntok(r["model_answer"]) if len(r["prompts"]) > 1 else 0)
                                   for r in s.values()])) for lab, s in systems.items()}
    chosen = json.loads((OUT / "v1_dev.json").read_text()) if (OUT / "v1_dev.json").exists() else None

    def table(ids: List[str], title: str) -> List[str]:
        out = [f"### {title} (n = {len(ids)})", "",
               "| System | F1 all | answerable | unanswerable | Δ all vs P | Δ all vs E | Δ answerable vs E | "
               "miss + gold fact (Δ vs E) | hit, no gold fact (Δ vs E) | abstain recall / false abstention | "
               "gen. tokens / turn in / out | in vs E |",
               "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
        for lab, s in systems.items():
            ok = [i for i in ids if s[i]["model_answer"] is not None]
            f = {i: f1(s[i]) for i in ok}
            fp, fe = {i: f1(P[i]) for i in ok}, {i: f1(E[i]) for i in ok}
            ans = [i for i in ok if not exs[i]["is_unanswerable"]]
            un = [i for i in ok if exs[i]["is_unanswerable"]]
            d = lambda sub, ref: fmt(paired_bootstrap_test([f[i] for i in sub], [ref[i] for i in sub])) if sub else "-"
            ab = {i: is_abstention(s[i]["model_answer"]) for i in ok}
            mg, hn = [i for i in ok if i in miss_gold], [i for i in ok if i in hit_nogold]
            out.append(
                f"| {lab} | {np.mean(list(f.values()))*100:.1f} | {np.mean([f[i] for i in ans])*100:.1f} | "
                f"{np.mean([f[i] for i in un])*100:.1f} | {'-' if s is P else d(ok, fp)} | {'-' if s is E else d(ok, fe)} | "
                f"{'-' if s is E else d(ans, fe)} | "
                f"{np.mean([f[i] for i in mg])*100:.1f} ({'-' if s is E else d(mg, fe)}) | "
                f"{np.mean([f[i] for i in hn])*100:.1f} ({'-' if s is E else d(hn, fe)}) | "
                f"{np.mean([ab[i] for i in un])*100:.1f} / {np.mean([ab[i] for i in ans])*100:.1f} | "
                f"{tok_in[lab]:.0f} / {tok_out[lab]:.0f} | {(tok_in[lab] / tok_in['E: passages + 30 facts'] - 1)*100:+.0f}% |")
        return out + [""]

    lines = ["# Step 7: Graph RAG variants (validation)", "",
             "gpt-5.4-nano, G2 + abstain(G0) in every system; P and E are the cached answers of the generator-input "
             "experiment. Δ: paired bootstrap difference with its 95% interval. The two subsets are fixed as defined "
             f"for E in the graph analysis: 'miss + gold fact' = gold section not in the passage top 5 and one of E's "
             f"facts from it ({len(miss_gold)} questions); 'hit, no gold fact' = gold section in the top 5 and none of "
             f"E's facts from it ({len(hit_nogold)}). Generator tokens per turn: G0 always, G2 when G0 does not abstain, "
             "counted from the prompts and answers (o200k_base), so P, E and the variants are counted the same way; "
             "the rewrite (~190 input tokens per turn) is the same for all and left out. No reasoning tokens: "
             "gpt-5.4-nano used none in the measured runs.", ""]
    if chosen:
        lines += ["V1 thresholds, chosen on dev-500 by F1 (ties go to the higher threshold): "
                  + "; ".join(f"k = {k}: {t}" for k, t in chosen["chosen_threshold"].items())
                  + ". Dev-500 F1 per setting: " + ", ".join(f"{k} {v*100:.1f}" for k, v in chosen["f1"].items()) + ".", ""]
    lines += table(list(E), "Full validation split")
    lines += table(held, "Held-out validation (dev-500 removed), for the tuned V1 settings")
    ctrl = ["### V1 against its random control (same number of facts per question)", "",
            "| k | set | Δ all [95% CI] | Δ answerable [95% CI] |", "| :--- | :--- | :---: | :---: |"]
    for k in KS:
        a, b = systems.get(f"V1: top {k} facts"), systems.get(f"V1 control: {k} random facts")
        if not a or not b:
            continue
        for set_name, ids in (("full", list(E)), ("held-out", held)):
            ans = [i for i in ids if not exs[i]["is_unanswerable"]]
            ctrl.append(f"| {k} | {set_name} | {fmt(paired_bootstrap_test([f1(a[i]) for i in ids], [f1(b[i]) for i in ids]))} | "
                        f"{fmt(paired_bootstrap_test([f1(a[i]) for i in ans], [f1(b[i]) for i in ans]))} |")
    lines += ctrl + [""]
    v1 = systems.get("V1: top 10 facts")
    v2 = [lab for lab in systems if lab.startswith("V2")]
    if v1 and v2:
        cmp = ["### V2 against V1 with k = 10 (paired, full validation)", "",
               "| System | Δ all | Δ answerable | Δ miss + gold fact | Δ hit, no gold fact | input tokens vs V1 |",
               "| :--- | :---: | :---: | :---: | :---: | :---: |"]
        for lab in v2:
            s2 = systems[lab]
            ids = [i for i in E if s2[i]["model_answer"] is not None and v1[i]["model_answer"] is not None]
            sub = lambda keep: fmt(paired_bootstrap_test([f1(s2[i]) for i in ids if keep(i)], [f1(v1[i]) for i in ids if keep(i)]))
            cmp.append(f"| {lab} | {sub(lambda i: True)} | {sub(lambda i: not exs[i]['is_unanswerable'])} | "
                       f"{sub(lambda i: i in miss_gold)} | {sub(lambda i: i in hit_nogold)} | "
                       f"{(tok_in[lab] / tok_in['V1: top 10 facts'] - 1)*100:+.0f}% |")
        lines += cmp + [""]
    # diagnostic (uses the gold sections, analysis only): share of questions with at least one fact
    # from a gold section, and with at least one fact from outside the top 5 passages
    gold = load_gold()
    diag = ["### Facts in the prompt (diagnostic, uses the gold sections)", "",
            "| System | questions with a fact from a gold section | of them in the 342 'miss + gold fact' questions | facts per question |",
            "| :--- | :---: | :---: | :---: |"]
    for lab, s in systems.items():
        if lab.startswith("P") or lab.startswith("V0"):
            continue
        has = {i: bool(fact_sections_of(s[i]["context"]) & gold[i]) for i in E}
        diag.append(f"| {lab} | {np.mean(list(has.values()))*100:.1f}% | {np.mean([has[i] for i in miss_gold])*100:.1f}% | "
                    f"{np.mean([n_facts(s[i]['context']) for i in E]):.1f} |")
    lines += diag + [""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["v0", "score", "v1-dev", "v1", "v2", "v3-retrieval", "report"])
    args = parser.parse_args()
    {"v0": run_v0, "score": score_facts, "v1-dev": run_v1_dev, "v1": run_v1, "v2": run_v2, "v3-retrieval": run_v3_retrieval, "report": report}[args.cmd]()


if __name__ == "__main__":
    main()
