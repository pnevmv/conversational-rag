"""Check that the demo builds the same contexts and prompts as the experiments (no LLM calls).

For 20 validation questions (seed 42), the stored rewrite and the gold history are fed to the demo
pipeline; its contexts and G0/G2 prompts must equal the stored ones byte for byte:
    P   rag_rewrite_rerank_v2.jsonl and generator_input/rag_rewrite_rerank_v2__G0 / __G2_kall
    E   step4_plus_facts.jsonl and generator_input/step4_plus_facts__G0 / __G2_kall
    V1  graph_rag/v1_k10.jsonl (context and the prompts actually sent)
    E with citations  sources/cite_validation.jsonl (G2 prompt)

    python demo/check_replay.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import PROJECT_ROOT, Pipeline  # noqa: E402

from src.data.loader import load_qa_pairs  # noqa: E402

VAL = PROJECT_ROOT / "experiments" / "results" / "validation"
N, SEED = 20, 42


def load(path: Path):
    return {r["example_id"]: r for r in map(json.loads, open(path, encoding="utf-8"))}


def first_diff(a: str, b: str) -> str:
    i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return f"at char {i}: demo {a[max(0, i - 40):i + 60]!r} | stored {b[max(0, i - 40):i + 60]!r}"


def main() -> None:
    e = load(VAL / "step4_plus_facts.jsonl")
    p = load(VAL / "rag_rewrite_rerank_v2.jsonl")
    gen = {k: load(VAL / "generator_input" / f"{k}.jsonl") for k in
           ("step4_plus_facts__G0", "step4_plus_facts__G2_kall", "rag_rewrite_rerank_v2__G0", "rag_rewrite_rerank_v2__G2_kall")}
    v1 = load(VAL / "graph_rag" / "v1_k10.jsonl")
    cite = load(VAL / "sources" / "cite_validation.jsonl")
    exs = {ex["example_id"]: ex for ex in load_qa_pairs(split="validation", max_examples=None)}

    ids = sorted(v1)
    rng = random.Random(SEED)
    first = [i for i in ids if not exs[i]["dialogue_history"]]
    later = [i for i in ids if exs[i]["dialogue_history"]]
    pick = rng.sample(first, 5) + rng.sample(later, N - 5)

    pipe = Pipeline()
    checks = fails = 0

    def check(name: str, i: str, demo: str, stored: str) -> None:
        nonlocal checks, fails
        checks += 1
        if demo != stored:
            fails += 1
            print(f"DIFF {name} {i}: {first_diff(demo, stored)}")

    for i in pick:
        ex, rw = exs[i], e[i]["rewritten_query"] or exs[i]["question"]
        q, hist = ex["question"], ex["dialogue_history"]
        ranking = pipe.passages(rw)
        for system, ctx_store, g0, g2 in (("P", p[i]["context"], "rag_rewrite_rerank_v2__G0", "rag_rewrite_rerank_v2__G2_kall"),
                                          ("E", e[i]["context"], "step4_plus_facts__G0", "step4_plus_facts__G2_kall")):
            facts = pipe.facts(rw, "E")["facts"] if system == "E" else []
            ctx = pipe.context(system, ranking, facts)
            check(f"{system} context", i, ctx, ctx_store)
            pr = pipe.prompts(system, ctx, q, hist, rw, cite=False)
            check(f"{system} G0", i, pr["G0"], gen[g0][i]["prompt"])
            check(f"{system} G2", i, pr["G2"], gen[g2][i]["prompt"])
            if system == "E" and cite.get(i, {}).get("prompt"):
                check("E cite G2", i, pipe.prompts("E", ctx, q, hist, rw, cite=True)["G2"], cite[i]["prompt"])
        facts = pipe.facts(rw, "V1")["facts"]
        ctx = pipe.context("V1", ranking, facts)
        check("V1 context", i, ctx, v1[i]["context"])
        pr = pipe.prompts("V1", ctx, q, hist, rw, cite=False)
        for k, stored in zip(("G0", "G2"), v1[i]["prompts"]):
            check(f"V1 {k}", i, pr[k], stored)

    turns = f"{len(pick)} questions ({sum(1 for i in pick if not exs[i]['dialogue_history'])} first turns)"
    print(f"\n{turns}: {checks - fails} of {checks} checks identical, {fails} differ")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
