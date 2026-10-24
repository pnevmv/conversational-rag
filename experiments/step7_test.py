"""Step 7, final run on the test split (run once, nothing tuned here).

Frozen systems, all with gpt-5.4-nano and G2 + abstain(G0):
    P   passages (rag_rewrite_rerank_v2)
    E   passages + up to 30 one-hop facts (step4_plus_facts)
    V1  passages + the 10 one-hop facts with the best cross-encoder score (k = 10, no threshold)

Contexts of P and E are the cached test contexts; V1 scores the candidate facts of the test
questions with the same cross-encoder and builds its context exactly as on validation.

    python experiments/step7_test.py run
    python experiments/step7_test.py report
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import experiments.graph_rag as gr
from experiments.evaluate_diagnostics import paired_bootstrap_test
from src.data.loader import load_qa_pairs
from src.evaluation.metrics import compute_metrics, is_abstention
from src.kg_rag.queries import RERANKER_CACHE_DIR

TEST = PROJECT_ROOT / "experiments" / "results" / "test"
OUT = TEST / "step7"
K = 10
SYSTEMS = {"p": "P: passages", "e": "E: passages + 30 facts", "v1_k10": "V1: passages + 10 facts"}


def setup() -> None:
    """Point the validation code at the test split."""
    gr._EXAMPLES = {ex["example_id"]: ex for ex in load_qa_pairs(split="test", max_examples=None)}
    gr.OUT = OUT


def run() -> None:
    setup()
    from src.rag import Reranker
    e_rows = gr.load(TEST / "step4_plus_facts.jsonl")
    p_rows = gr.load(TEST / "rag_rewrite_rerank_v2.jsonl")
    rw = {r["example_id"]: r["rewritten_query"] or r["question"] for r in e_rows}
    # V1: cross-encoder score of every one-hop candidate fact, top 10 kept
    g = gr.kg()
    queries, cands, ids = [], [], []
    for r in e_rows:
        rel = sorted({i for l in r["linked_entities"] for i in g.adjacent[l["entity_id"]]})
        ids.append(r["example_id"])
        queries.append(rw[r["example_id"]])
        cands.append([{"text": gr.fact_text(g.relations[i]), "relation_index": i} for i in rel])
    print(f"scoring {sum(len(c) for c in cands)} (query, fact) pairs", flush=True)
    ranked = Reranker(cache_dir=RERANKER_CACHE_DIR).rerank_many(queries, cands, top_k=K)
    v1 = {}
    for r, (docs, _) in zip(e_rows, ranked):
        sections = r["context"].partition("\n\nFacts:\n")[0]
        keep = [d["relation_index"] for d in docs]
        v1[r["example_id"]] = sections + ("\n\nFacts:\n" + gr.facts_block(keep) if keep else "")
    gr.generate("p", {r["example_id"]: r["context"] for r in p_rows}, rw)
    gr.generate("e", {r["example_id"]: r["context"] for r in e_rows}, rw)
    gr.generate("v1_k10", v1, rw)


def report() -> None:
    setup()
    enc = tiktoken.get_encoding("o200k_base")
    ntok = lambda s: len(enc.encode(s or "", disallowed_special=()))
    runs = {k: {r["example_id"]: r for r in gr.load(OUT / f"{k}.jsonl")} for k in SYSTEMS}
    ids = [i for i in runs["p"] if all(runs[k][i]["model_answer"] is not None for k in SYSTEMS)]
    missing = len(runs["p"]) - len(ids)
    f1 = {k: {i: compute_metrics(runs[k][i]["model_answer"], runs[k][i]["reference_answer"])["f1"] for i in ids} for k in SYSTEMS}
    un = [i for i in ids if runs["p"][i]["is_unanswerable"]]
    ans = [i for i in ids if not runs["p"][i]["is_unanswerable"]]
    fmt = lambda t: f"{t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]"
    tok = {k: float(np.mean([sum(ntok(p) for p in runs[k][i]["prompts"]) for i in ids])) for k in SYSTEMS}
    lines = ["# Step 7: final systems on the test split", "",
             f"Test split of MultiDoc2Dial, {len(runs['p'])} questions ({len(un)} unanswerable), run once with the "
             "systems frozen on validation (experiments/results/validation/graph_rag/decisions.md); nothing was tuned on the test split. All systems use gpt-5.4-nano with the dialogue "
             "history and the abstention decision of the prompt without history (G2 + abstain(G0)), the same rewrites "
             "and passages, and differ only in the graph facts. Δ: paired bootstrap difference with its 95% interval. "
             "Input tokens per turn: generator calls only (G0 always, G2 when G0 does not abstain), counted from the "
             "prompts (o200k_base); the rewrite is the same for all."
             + (f" {missing} questions without an answer from one of the systems are left out." if missing else ""), "",
             "| System | F1 all | answerable | unanswerable | abstain recall / false abstention | input tokens / turn |",
             "| :--- | :---: | :---: | :---: | :---: | :---: |"]
    for k, label in SYSTEMS.items():
        ab = {i: is_abstention(runs[k][i]["model_answer"]) for i in ids}
        lines.append(f"| {label} | {np.mean([f1[k][i] for i in ids])*100:.1f} | {np.mean([f1[k][i] for i in ans])*100:.1f} | "
                     f"{np.mean([f1[k][i] for i in un])*100:.1f} | {np.mean([ab[i] for i in un])*100:.1f} / "
                     f"{np.mean([ab[i] for i in ans])*100:.1f} | {tok[k]:,.0f} ({(tok[k] / tok['e'] - 1)*100:+.0f}% vs E) |")
    lines += ["", "| Comparison | Δ all | Δ answerable | Δ unanswerable |", "| :--- | :---: | :---: | :---: |"]
    for a, b in (("v1_k10", "p"), ("e", "p"), ("v1_k10", "e")):
        d = lambda sub: fmt(paired_bootstrap_test([f1[a][i] for i in sub], [f1[b][i] for i in sub]))
        lines.append(f"| {SYSTEMS[a].split(':')[0]} vs {SYSTEMS[b].split(':')[0]} | {d(ids)} | {d(ans)} | {d(un)} |")
    lines.append("")
    (TEST / "step7_final.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["run", "report"])
    args = parser.parse_args()
    run() if args.cmd == "run" else report()


if __name__ == "__main__":
    main()
