"""Evaluate the phase 2 pipelines against the Step 4 best (F1, recall, abstention,
splits, paired bootstrap). Writes experiments/kg_rag/phase2_qa.json.

    python -m src.kg_rag.eval_qa
"""
import json
from typing import Any, Dict, List

import numpy as np

from experiments.evaluate_diagnostics import bootstrap_ci, evaluate_file, load_records, paired_bootstrap_test
from experiments.run_dev_subset import RESULTS_DIR
from src.evaluation.metrics import compute_metrics, is_abstention
from src.kg_rag.queries import OUT_DIR

BASELINE = "rag_rewrite_rerank_v2"
PIPELINES = {
    BASELINE: "Step 4 best: Hybrid + Rewrite + Rerank",
    "rag_rewrite_baseline_v2": "Step 4 without reranker",
    "rag_rewrite_rerank": "Step 4 best with the old prompt",
    "kg_sections": "A: KG -> sections",
    "kg_sections_1hop": "A: KG -> sections, 1-hop",
    "kg_facts": "B: KG facts",
    "kg_hybrid": "C: hybrid (A + Step 4, reranked)",
    "kg_rerank": "D: A's top-50 reranked",
    "step4_plus_facts": "E: Step 4 sections + KG facts",
    "step4_plus_random_facts": "E-random: Step 4 sections + random same-domain facts",
}
E, E_RANDOM = "step4_plus_facts", "step4_plus_random_facts"


def per_example(path) -> Dict[str, Dict[str, Any]]:
    out = {}
    for r in load_records(path):
        ans = r.get("model_answer") or ""
        out[r["example_id"]] = {**r, "f1": compute_metrics(ans, r["reference_answer"])["f1"],
                                "abstained": is_abstention(ans)}
    return out


def split_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0}
    return {"n": len(rows), "f1": bootstrap_ci([r["f1"] for r in rows]),
            "r1": float(np.mean([r["recall_at_1"] for r in rows])),
            "r5": float(np.mean([r["recall_at_5"] for r in rows])),
            "abstain_rate": float(np.mean([r["abstained"] for r in rows]))}


def main() -> None:
    import argparse
    from src.kg_rag.run_qa import results_dir
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev500", "validation", "test"], default="dev500")
    split = parser.parse_args().split
    rdir = results_dir(split)
    pipelines = {k: v for k, v in PIPELINES.items() if (rdir / f"{k}.jsonl").exists()}
    data = {name: per_example(rdir / f"{name}.jsonl") for name in pipelines}
    ids = list(data[BASELINE])
    assert all(set(d) == set(ids) for d in data.values()), "pipelines cover different examples"

    base_hit = {i: data[BASELINE][i]["recall_at_5"] > 0 for i in ids}
    splits = {
        "all": lambda r: True,
        "step4_hit": lambda r: not r["is_unanswerable"] and base_hit[r["example_id"]],
        "step4_miss": lambda r: not r["is_unanswerable"] and not base_hit[r["example_id"]],
        "same_doc": lambda r: not r["is_doc_switch"],
        "doc_switch": lambda r: r["is_doc_switch"],
        "answerable": lambda r: not r["is_unanswerable"],
        "unanswerable": lambda r: r["is_unanswerable"],
    }
    result: Dict[str, Any] = {"split": split, "baseline": BASELINE, "pipelines": {}}
    for name, label in pipelines.items():
        d = data[name]
        rows = [d[i] for i in ids]
        _, diag = evaluate_file(rdir / f"{name}.jsonl")
        diag.pop("_per_example_f1", None)
        res = {"label": label, "diagnostics": diag,
               "recall_at_1": float(np.mean([r["recall_at_1"] for r in rows])),
               "domain_recall": float(np.mean([r["domain_recall"] for r in rows if r.get("domain_recall") is not None])),
               "abstain_rate": float(np.mean([r["abstained"] for r in rows])),
               "splits": {s: split_stats([r for r in rows if f(r)]) for s, f in splits.items()},
               "by_domain": {dom: split_stats([r for r in rows if r["domain"] == dom])
                             for dom in sorted({r["domain"] for r in rows})},
               "prompt_chars": float(np.mean([len(r.get("prompt") or "") for r in rows]))}
        if name != BASELINE:
            base = data[BASELINE]
            res["paired_vs_baseline"] = {
                s: paired_bootstrap_test([d[i]["f1"] for i in ids if f(d[i])], [base[i]["f1"] for i in ids if f(d[i])])
                for s, f in splits.items()}
        if name == E_RANDOM and E in data:
            res["paired_vs_E"] = {
                s: paired_bootstrap_test([d[i]["f1"] for i in ids if f(d[i])], [data[E][i]["f1"] for i in ids if f(d[i])])
                for s, f in splits.items()}
        if name in ("kg_hybrid", "kg_rerank"):
            changed = [i for i in ids if d[i]["context"] != data[BASELINE][i]["context"]]
            res["changed_context"] = {
                "n": len(changed),
                "new_sections_in_top5": float(np.mean([d[i]["new_vs_step4"] for i in ids])),
                "f1_hybrid": float(np.mean([d[i]["f1"] for i in changed])) if changed else None,
                "f1_baseline": float(np.mean([data[BASELINE][i]["f1"] for i in changed])) if changed else None,
                "r5_hybrid": float(np.mean([d[i]["recall_at_5"] for i in changed])) if changed else None,
                "r5_baseline": float(np.mean([data[BASELINE][i]["recall_at_5"] for i in changed])) if changed else None,
                "paired": paired_bootstrap_test([d[i]["f1"] for i in changed],
                                                [data[BASELINE][i]["f1"] for i in changed]) if changed else None,
            }
        if name in (E, E_RANDOM):
            def by_facts(flag):
                sub = [i for i in ids if not d[i]["is_unanswerable"] and (d[i]["facts_context_recall"] > 0) == flag]
                return {"n": len(sub), "f1": float(np.mean([d[i]["f1"] for i in sub])),
                        "f1_baseline": float(np.mean([data[BASELINE][i]["f1"] for i in sub])),
                        "paired": paired_bootstrap_test([d[i]["f1"] for i in sub],
                                                        [data[BASELINE][i]["f1"] for i in sub])}
            res["by_facts_gold"] = {"facts_reach_gold": by_facts(True), "facts_miss_gold": by_facts(False)}
            res["mean_facts"] = float(np.mean([r["n_facts"] for r in rows]))
        if name == "kg_facts":
            res["context_recall"] = float(np.mean([r["context_recall"] for r in rows]))
            res["mean_facts"] = float(np.mean([r["n_facts"] for r in rows]))
        result["pipelines"][name] = res

    out_file = OUT_DIR / "phase2_qa.json" if split == "dev500" else rdir / "kg_qa_summary.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

    def pct(x):
        return f"{x * 100:.1f}"
    print("| Pipeline | R@1 | R@5 | Domain R | F1 [CI] | F1 hit (n) | F1 miss (n) | Abstain | Abst. rec. | False abst. | ΔF1 vs Step 4 [CI] p |")
    for name, r in result["pipelines"].items():
        dg = r["diagnostics"]
        f1 = dg["f1"]
        hit = dg["f1_hit"]; miss = dg["f1_miss"]
        p = r.get("paired_vs_baseline", {}).get("all")
        delta = f"{p['mean_diff']*100:+.1f} [{p['ci_low']*100:.1f}, {p['ci_high']*100:.1f}] p={p['p_value']:.3f}" if p else "—"
        print(f"| {r['label']} | {pct(r['recall_at_1'])} | {pct(dg['r5']['mean'])} | {pct(r['domain_recall'])} | "
              f"{pct(f1['mean'])} [{pct(f1['ci_low'])}, {pct(f1['ci_high'])}] | "
              f"{pct(hit['ci']['mean'])} ({hit['n']}) | {pct(miss['ci']['mean'])} ({miss['n']}) | "
              f"{pct(r['abstain_rate'])} | {pct(dg['abstain_recall'])} | {pct(dg['false_abstention'])} | {delta} |")
    print()
    for s in ("step4_hit", "step4_miss", "same_doc", "doc_switch", "unanswerable"):
        print(f"--- {s}")
        for name, r in result["pipelines"].items():
            st = r["splits"][s]
            p = r.get("paired_vs_baseline", {}).get(s)
            delta = f"  Δ {p['mean_diff']*100:+.1f} [{p['ci_low']*100:.1f}, {p['ci_high']*100:.1f}] p={p['p_value']:.3f}" if p else ""
            print(f"  {name:22} n={st['n']:3}  F1 {pct(st['f1']['mean'])} [{pct(st['f1']['ci_low'])}, {pct(st['f1']['ci_high'])}]"
                  f"  R@5 {pct(st['r5'])}  abstain {pct(st['abstain_rate'])}{delta}")
    print("--- by domain (F1)")
    for name, r in result["pipelines"].items():
        print(f"  {name:22} " + "  ".join(f"{d} {pct(v['f1']['mean'])}" for d, v in r["by_domain"].items()))
    P = result["pipelines"]
    for nm in ("kg_rerank", "kg_hybrid"):
        if nm in P:
            cc = P[nm]["changed_context"]
            print(f"--- {nm}: {cc['n']} examples with a different context; new sections in top-5 {cc['new_sections_in_top5']:.2f}; "
                  f"F1 {pct(cc['f1_hybrid'])} vs {pct(cc['f1_baseline'])}; R@5 {pct(cc['r5_hybrid'])} vs {pct(cc['r5_baseline'])}")
    for nm in (E, E_RANDOM):
        if nm in P:
            print(f"--- {nm} by whether the facts reach a gold section:", json.dumps(P[nm]["by_facts_gold"], indent=1))
    if E_RANDOM in P and "paired_vs_E" in P[E_RANDOM]:
        print("--- E-random vs E")
        for s_, t in P[E_RANDOM]["paired_vs_E"].items():
            print(f"  {s_:12} n={t['n_paired']:4}  Δ {t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]")

if __name__ == "__main__":
    main()
