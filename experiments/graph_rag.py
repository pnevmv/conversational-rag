"""Step 7, Graph RAG variants on the validation split (plans/step7-graph-rag.md).

Every variant uses gpt-5.4-nano with G2 + abstain(G0): G0 (current user turn) on every
question, G2 (whole gold dialogue history) when G0 does not abstain; on first turns the two
prompts are the same. Rewrites, passages and linked entities come from the cache.

    V0   graph facts only (B) with dialogue history
    V1   passages + the top-k one-hop facts by cross-encoder score (k = 5, 10), facts below a
         score threshold dropped (threshold chosen on dev-500), with a random-facts control

    python experiments/graph_rag.py v0
    python experiments/graph_rag.py score          # cross-encoder score of every candidate fact
    python experiments/graph_rag.py v1-dev         # threshold per k on dev-500
    python experiments/graph_rag.py v1             # full validation, chosen thresholds + controls
    python experiments/graph_rag.py report
"""
import argparse
import json
import random
import re
import sys
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


# ---------------------------------------------------------------------------- report
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
                        ("v1_k10_random", "V1 control: 10 random facts")]:
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
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["v0", "score", "v1-dev", "v1", "report"])
    args = parser.parse_args()
    {"v0": run_v0, "score": score_facts, "v1-dev": run_v1_dev, "v1": run_v1, "report": report}[args.cmd]()


if __name__ == "__main__":
    main()
