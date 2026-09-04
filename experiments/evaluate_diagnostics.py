"""Diagnostic evaluation: oracle ceiling, F1 hit/miss, abstention metrics.

Processes one or more experiment JSONL files and produces:
  - F1 and R@5 with 95% bootstrap CIs
  - F1 split by retrieval hit (gold section in top-5) vs miss
  - Abstain recall, false-abstention rate, abstain precision
  - Paired bootstrap test (Hybrid+Rewrite vs Hybrid)
  - Summary JSON + Markdown table

Usage:
    python experiments/evaluate_diagnostics.py \\
        --inputs experiments/results/llm_baseline_full.jsonl \\
                 experiments/results/oracle_context_full.jsonl \\
                 experiments/results/rag_baseline_full.jsonl \\
                 ...
    # or use the default set (all *_full.jsonl + oracle):
    python experiments/evaluate_diagnostics.py
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.metrics import compute_metrics, is_abstention

RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"

DEFAULT_INPUTS = [
    RESULTS_DIR / "llm_baseline_full.jsonl",
    RESULTS_DIR / "oracle_context_full.jsonl",
    RESULTS_DIR / "rag_baseline_full.jsonl",
    RESULTS_DIR / "rag_dense_baseline_full.jsonl",
    RESULTS_DIR / "rag_hybrid_baseline_full.jsonl",
    RESULTS_DIR / "rag_rewrite_baseline_full.jsonl",
]

DISPLAY_NAMES = {
    "llm_baseline_full": "LLM-only",
    "oracle_context_full": "Oracle",
    "rag_baseline_full": "RAG BM25",
    "rag_dense_baseline_full": "RAG Dense",
    "rag_hybrid_baseline_full": "RAG Hybrid",
    "rag_rewrite_baseline_full": "RAG Hybrid+Rewrite",
    # short (50-example) variants
    "llm_baseline": "LLM-only",
    "oracle_context": "Oracle",
    "rag_baseline": "RAG BM25",
    "rag_dense_baseline": "RAG Dense",
    "rag_hybrid_baseline": "RAG Hybrid",
    "rag_rewrite_baseline": "RAG Hybrid+Rewrite",
    # dev_500 variants
    "rag_bm25_baseline": "RAG BM25",
    # dev_500 new-prompt variants
    "oracle_context_v2": "Oracle (agent prompt)",
    "rag_rewrite_baseline_v2": "RAG Hybrid+Rewrite (agent prompt)",
    # dev_500 reranker variants
    "rag_rewrite_rerank": "RAG Hybrid+Rewrite+Rerank",
    "rag_rewrite_rerank_v2": "RAG Hybrid+Rewrite+Rerank (agent prompt)",
}


# ---------------------------------------------------------------------------
# Core statistics helpers
# ---------------------------------------------------------------------------

def bootstrap_ci(
    values: List[float],
    n_boot: int = 1000,
    ci: float = 95.0,
    seed: int = 42,
) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    arr = np.array(values, dtype=float)
    rng = np.random.default_rng(seed)
    boots = np.array([
        rng.choice(arr, size=len(arr), replace=True).mean()
        for _ in range(n_boot)
    ])
    alpha = (100.0 - ci) / 2.0
    return {
        "mean": float(arr.mean()),
        "ci_low": float(np.percentile(boots, alpha)),
        "ci_high": float(np.percentile(boots, 100.0 - alpha)),
    }


def paired_bootstrap_test(
    scores_a: List[float],
    scores_b: List[float],
    n_boot: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Paired bootstrap test: CI of mean(a) - mean(b), p-value for a > b."""
    assert len(scores_a) == len(scores_b), "Paired arrays must have equal length"
    diff = np.array(scores_a, dtype=float) - np.array(scores_b, dtype=float)
    rng = np.random.default_rng(seed)
    boot_diffs = np.array([
        rng.choice(diff, size=len(diff), replace=True).mean()
        for _ in range(n_boot)
    ])
    return {
        "mean_diff": float(diff.mean()),
        "ci_low": float(np.percentile(boot_diffs, 2.5)),
        "ci_high": float(np.percentile(boot_diffs, 97.5)),
        "p_value": float((boot_diffs <= 0.0).mean()),
        "n_paired": len(diff),
    }


# ---------------------------------------------------------------------------
# Per-file evaluation
# ---------------------------------------------------------------------------

def load_records(path: Path) -> List[Dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def evaluate_file(
    path: Path,
    n_boot: int = 1000,
) -> Tuple[str, Dict[str, Any]]:
    stem = path.stem
    name = DISPLAY_NAMES.get(stem, stem)
    records = load_records(path)

    rows: List[Dict[str, Any]] = []
    skipped = 0

    for rec in records:
        if rec.get("status") not in ("success", "abstained", "cached") or rec.get("model_answer") is None:
            skipped += 1
            continue
        answer = rec["model_answer"]
        reference = rec["reference_answer"]
        scores = compute_metrics(answer, reference)
        abstained = is_abstention(answer)
        r5 = rec.get("recall_at_5")
        is_unans = rec.get("is_unanswerable", False)
        # retrieval hit: gold span found in top-5; None for no-retrieval experiments
        ret_hit: Optional[bool] = (r5 > 0.0) if r5 is not None else None

        rows.append({
            "example_id": rec["example_id"],
            "f1": scores["f1"],
            "exact_match": scores["exact_match"],
            "is_unanswerable": is_unans,
            "is_doc_switch": rec.get("is_doc_switch", False),
            "abstained": abstained,
            "retrieval_hit": ret_hit,
            "recall_at_5": r5,
        })

    answerable = [r for r in rows if not r["is_unanswerable"]]
    unanswerable = [r for r in rows if r["is_unanswerable"]]

    # F1 overall
    f1_all_ci = bootstrap_ci([r["f1"] for r in rows], n_boot=n_boot)

    # R@5 (only rows that have it)
    r5_vals = [r["recall_at_5"] for r in rows if r["recall_at_5"] is not None]
    r5_ci = bootstrap_ci(r5_vals, n_boot=n_boot) if r5_vals else None

    # F1 hit / miss (answerable rows that have retrieval info)
    ans_with_ret = [r for r in answerable if r["retrieval_hit"] is not None]
    hit_rows = [r for r in ans_with_ret if r["retrieval_hit"]]
    miss_rows = [r for r in ans_with_ret if not r["retrieval_hit"]]
    f1_hit_ci = bootstrap_ci([r["f1"] for r in hit_rows], n_boot=n_boot) if hit_rows else None
    f1_miss_ci = bootstrap_ci([r["f1"] for r in miss_rows], n_boot=n_boot) if miss_rows else None

    # Abstention metrics
    n_unans = len(unanswerable)
    n_ans = len(answerable)
    n_abstained_unans = sum(1 for r in unanswerable if r["abstained"])
    n_abstained_ans = sum(1 for r in answerable if r["abstained"])
    n_abstained_total = sum(1 for r in rows if r["abstained"])

    abstain_recall = n_abstained_unans / n_unans if n_unans else None
    false_abstention = n_abstained_ans / n_ans if n_ans else None
    abstain_precision = n_abstained_unans / n_abstained_total if n_abstained_total else None

    abstain_recall_ci = bootstrap_ci(
        [float(r["abstained"]) for r in unanswerable], n_boot=n_boot
    ) if n_unans else None

    result = {
        "name": name,
        "path": str(path),
        "n_total": len(rows) + skipped,
        "n_evaluated": len(rows),
        "n_skipped": skipped,
        "n_unanswerable": n_unans,
        "n_answerable": n_ans,
        "f1": f1_all_ci,
        "r5": r5_ci,
        "f1_hit": {"ci": f1_hit_ci, "n": len(hit_rows)} if hit_rows else None,
        "f1_miss": {"ci": f1_miss_ci, "n": len(miss_rows)} if miss_rows else None,
        "abstain_recall": abstain_recall,
        "abstain_recall_ci": abstain_recall_ci,
        "false_abstention": false_abstention,
        "abstain_precision": abstain_precision,
        "n_abstained": n_abstained_total,
        # keep per-example F1 for paired test (indexed by example_id)
        "_per_example_f1": {r["example_id"]: r["f1"] for r in rows},
    }
    return stem, result


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _pct(val: Optional[float], ci: Optional[Dict] = None, n: Optional[int] = None) -> str:
    if val is None:
        return "—"
    s = f"{val * 100:.1f}"
    if ci:
        s += f" [{ci['ci_low']*100:.1f}–{ci['ci_high']*100:.1f}]"
    if n is not None:
        s += f" (n={n})"
    return s


def render_markdown(
    results: Dict[str, Dict],
    paired: Optional[Dict] = None,
    paired_list: Optional[List[Dict]] = None,
    title: str = "Diagnostic Evaluation",
) -> str:
    order = [
        "llm_baseline_full", "oracle_context_full",
        "rag_baseline_full", "rag_dense_baseline_full",
        "rag_hybrid_baseline_full", "rag_rewrite_baseline_full",
        "llm_baseline", "oracle_context", "oracle_context_v2",
        "rag_bm25_baseline", "rag_baseline", "rag_dense_baseline",
        "rag_hybrid_baseline", "rag_rewrite_baseline", "rag_rewrite_baseline_v2",
        "rag_rewrite_rerank", "rag_rewrite_rerank_v2",
    ]
    keys = [k for k in order if k in results] + [k for k in results if k not in order]

    header = (
        "| Experiment | n | F1% [95% CI] | F1-hit% [CI] (n) | F1-miss% [CI] (n)"
        " | R@5% [CI] | Abstain Rec% [CI] | False Abstain% | Abstain Prec% |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    rows_md = []
    for k in keys:
        r = results[k]
        f1_hit = r.get("f1_hit")
        f1_miss = r.get("f1_miss")
        rows_md.append(
            f"| {r['name']} "
            f"| {r['n_evaluated']} "
            f"| {_pct(r['f1']['mean'], r['f1'])} "
            f"| {_pct(f1_hit['ci']['mean'] if f1_hit else None, f1_hit['ci'] if f1_hit else None, f1_hit['n'] if f1_hit else None)} "
            f"| {_pct(f1_miss['ci']['mean'] if f1_miss else None, f1_miss['ci'] if f1_miss else None, f1_miss['n'] if f1_miss else None)} "
            f"| {_pct(r['r5']['mean'] if r.get('r5') else None, r.get('r5'))} "
            f"| {_pct(r['abstain_recall'], r.get('abstain_recall_ci'))} "
            f"| {_pct(r['false_abstention'])} "
            f"| {_pct(r['abstain_precision'])} |"
        )

    lines = [f"# {title}\n", header + "\n".join(rows_md)]

    # Support both old single `paired` arg and new `paired_list`
    all_tests = []
    if paired_list:
        all_tests = paired_list
    elif paired:
        all_tests = [paired]

    for pt in all_tests:
        a = pt["system_a"]
        b = pt["system_b"]
        t = pt["test"]
        sig = "**significant**" if t["p_value"] < 0.05 else "not significant"
        lines.append(
            f"\n## Paired Bootstrap Test: {a} vs {b} (Token F1, n={t['n_paired']})\n\n"
            f"Mean difference: {t['mean_diff']*100:+.2f} pp  "
            f"95% CI [{t['ci_low']*100:.2f}–{t['ci_high']*100:.2f}]  "
            f"p={t['p_value']:.3f} ({sig})"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_diagnostics(
    input_paths: List[Path],
    output_json: Path,
    output_md: Path,
    n_boot: int = 1000,
    paired_a: str = "rag_rewrite_baseline_full",
    paired_b: str = "rag_hybrid_baseline_full",
    extra_paired: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Evaluate all files and write JSON + Markdown.

    extra_paired: additional (stem_a, stem_b) pairs beyond the default one.
    """
    results: Dict[str, Dict] = {}
    for path in input_paths:
        if not path.exists():
            print(f"  Skipping (not found): {path}")
            continue
        print(f"  Evaluating {path.name}...")
        stem, r = evaluate_file(path, n_boot=n_boot)
        results[stem] = r

    def _find(key: str) -> Optional[str]:
        if key in results:
            return key
        short = key.replace("_full", "")
        return short if short in results else None

    def _make_paired(ka: str, kb: str) -> Optional[Dict]:
        ka2, kb2 = _find(ka), _find(kb)
        if not (ka2 and kb2):
            return None
        ra = results[ka2]["_per_example_f1"]
        rb = results[kb2]["_per_example_f1"]
        shared = sorted(set(ra) & set(rb))
        if not shared:
            return None
        scores_a = [ra[eid] for eid in shared]
        scores_b = [rb[eid] for eid in shared]
        pt = {
            "system_a": results[ka2]["name"],
            "system_b": results[kb2]["name"],
            "test": paired_bootstrap_test(scores_a, scores_b, n_boot=n_boot),
        }
        print(
            f"\n  Paired test ({pt['system_a']} vs {pt['system_b']}): "
            f"Δ={pt['test']['mean_diff']*100:+.2f} pp  "
            f"p={pt['test']['p_value']:.3f}"
        )
        return pt

    paired_list: List[Dict] = []
    pt = _make_paired(paired_a, paired_b)
    if pt:
        paired_list.append(pt)
    for a, b in (extra_paired or []):
        pt = _make_paired(a, b)
        if pt:
            paired_list.append(pt)

    # Strip internal per-example data before serialising
    clean_results = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                     for k, v in results.items()}

    payload: Dict[str, Any] = {"experiments": clean_results}
    if len(paired_list) == 1:
        payload["paired_test"] = paired_list[0]
    elif paired_list:
        payload["paired_tests"] = paired_list

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON saved: {output_json}")

    md = render_markdown(
        results,
        paired_list=paired_list or None,
        title="Diagnostic Evaluation — MultiDoc2Dial",
    )
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  Markdown saved: {output_md}")

    return payload


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run diagnostic evaluation across experiments.")
    parser.add_argument(
        "--inputs", nargs="+", default=None,
        help="JSONL files to evaluate (default: all *_full.jsonl + oracle in results/)",
    )
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--n-boot", type=int, default=1000)
    args = parser.parse_args()

    if args.inputs:
        input_paths = [Path(p) for p in args.inputs]
    else:
        input_paths = [p for p in DEFAULT_INPUTS if p.exists()]

    # Derive output filenames from the input set
    suffix = "_full" if any("_full" in p.stem for p in input_paths) else ""
    out_json = Path(args.output_json) if args.output_json else (
        RESULTS_DIR / f"diagnostics{suffix}.json"
    )
    out_md = Path(args.output_md) if args.output_md else (
        RESULTS_DIR / f"diagnostics{suffix}.md"
    )

    print("Running diagnostics...\n")
    run_diagnostics(
        input_paths=input_paths,
        output_json=out_json,
        output_md=out_md,
        n_boot=args.n_boot,
    )


if __name__ == "__main__":
    main()
