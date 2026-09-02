import json
import sys
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.metrics import compute_metrics

DEFAULT_INPUT = PROJECT_ROOT / "experiments" / "results" / "llm_baseline.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments" / "results" / "llm_baseline_evaluation.json"


def bootstrap_ci(
    values: List[float],
    n_boot: int = 1000,
    ci: float = 95.0,
    seed: int = 42,
) -> Dict[str, float]:
    """Percentile bootstrap CI for the mean of values."""
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


def evaluate(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
    n_boot: int = 1000,
) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    UNANSWERABLE = "Unfortunately, no relevant information is found."

    results: List[Dict[str, Any]] = []
    skipped = 0

    for rec in records:
        if rec.get("status") not in ("success", "abstained") or rec.get("model_answer") is None:
            skipped += 1
            continue

        scores = compute_metrics(
            prediction=rec["model_answer"],
            reference=rec["reference_answer"],
        )
        is_unans = rec.get("is_unanswerable", rec["reference_answer"] == UNANSWERABLE)
        abstained = rec["model_answer"].strip() == UNANSWERABLE

        results.append({
            "example_id": rec["example_id"],
            "domain": rec["domain"],
            "question": rec["question"],
            "reference_answer": rec["reference_answer"],
            "model_answer": rec["model_answer"],
            "is_unanswerable": is_unans,
            "is_doc_switch": rec.get("is_doc_switch", False),
            "abstained": abstained,
            "exact_match": scores["exact_match"],
            "f1": scores["f1"],
            "recall_at_1": rec.get("recall_at_1"),
            "recall_at_5": rec.get("recall_at_5"),
            "domain_recall": rec.get("domain_recall"),
            "top_retrieval_score": rec.get("top_retrieval_score"),
        })

    answerable = [r for r in results if not r["is_unanswerable"]]
    unanswerable = [r for r in results if r["is_unanswerable"]]
    doc_switch = [r for r in results if r["is_doc_switch"]]
    same_doc = [r for r in results if not r["is_doc_switch"]]

    def _agg(subset: List[Dict]) -> Dict[str, Any]:
        if not subset:
            return {"f1": 0.0, "exact_match": 0.0, "n": 0}
        agg: Dict[str, Any] = {
            "n": len(subset),
            "exact_match": float(np.mean([r["exact_match"] for r in subset])),
            "f1": float(np.mean([r["f1"] for r in subset])),
            "f1_ci": bootstrap_ci([r["f1"] for r in subset], n_boot=n_boot),
            "exact_match_ci": bootstrap_ci([r["exact_match"] for r in subset], n_boot=n_boot),
        }
        for key in ("recall_at_1", "recall_at_5", "domain_recall"):
            vals = [r[key] for r in subset if r.get(key) is not None]
            if vals:
                agg[key] = float(np.mean(vals))
                agg[f"{key}_ci"] = bootstrap_ci(vals, n_boot=n_boot)
        return agg

    abstain_vals = [float(r["abstained"]) for r in unanswerable]
    abstain_rate = float(np.mean(abstain_vals)) if abstain_vals else 0.0
    abstain_ci = bootstrap_ci(abstain_vals, n_boot=n_boot) if abstain_vals else None

    report = {
        "experiment": input_path.stem.replace("_evaluation", ""),
        "input_file": str(input_path),
        "total_examples": len(records),
        "evaluated": len(results),
        "skipped": skipped,
        "aggregate": _agg(results),
        "answerable": _agg(answerable),
        "unanswerable": {
            **_agg(unanswerable),
            "abstain_rate": abstain_rate,
            "abstain_rate_ci": abstain_ci,
        },
        "doc_switch": _agg(doc_switch),
        "same_doc": _agg(same_doc),
        "per_example": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def _fmt(val: float, ci: Optional[Dict] = None) -> str:
    s = f"{val*100:.2f}%"
    if ci:
        s += f" [{ci['ci_low']*100:.2f}–{ci['ci_high']*100:.2f}]"
    return s


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate experiment predictions.")
    parser.add_argument("--input", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--n-boot", type=int, default=1000,
                        help="Bootstrap resamples for CIs (default 1000)")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else DEFAULT_INPUT
    output_path = Path(args.output) if args.output else (
        input_path.parent / (input_path.stem + "_evaluation.json")
    )

    report = evaluate(input_path=input_path, output_path=output_path, n_boot=args.n_boot)

    agg = report["aggregate"]
    ans = report["answerable"]
    unans = report["unanswerable"]
    ds = report["doc_switch"]
    sd = report["same_doc"]

    print("----------------------------------------")
    print(f"Evaluated : {report['evaluated']} / {report['total_examples']}")
    print(f"Skipped   : {report['skipped']}")
    print(f"Exact Match: {_fmt(agg['exact_match'], agg.get('exact_match_ci'))}")
    print(f"Token F1   : {_fmt(agg['f1'], agg.get('f1_ci'))}")
    if "recall_at_1" in agg:
        print(f"Recall@1   : {_fmt(agg['recall_at_1'], agg.get('recall_at_1_ci'))}")
    if "recall_at_5" in agg:
        print(f"Recall@5   : {_fmt(agg['recall_at_5'], agg.get('recall_at_5_ci'))}")
    if "domain_recall" in agg:
        print(f"Domain R@5 : {_fmt(agg['domain_recall'], agg.get('domain_recall_ci'))}")
    if ans["n"]:
        print(f"  Answerable   (n={ans['n']:4d}): F1 {_fmt(ans['f1'], ans.get('f1_ci'))}")
    if unans["n"]:
        ar = unans["abstain_rate"]
        ar_ci = unans.get("abstain_rate_ci")
        print(f"  Unanswerable (n={unans['n']:4d}): F1 {_fmt(unans['f1'], unans.get('f1_ci'))}  abstain {_fmt(ar, ar_ci)}")
    if ds["n"]:
        r5 = f"  R@5 {_fmt(ds['recall_at_5'], ds.get('recall_at_5_ci'))}" if "recall_at_5" in ds else ""
        print(f"  Doc-switch   (n={ds['n']:4d}): F1 {_fmt(ds['f1'], ds.get('f1_ci'))}{r5}")
    if sd["n"]:
        r5 = f"  R@5 {_fmt(sd['recall_at_5'], sd.get('recall_at_5_ci'))}" if "recall_at_5" in sd else ""
        print(f"  Same-doc     (n={sd['n']:4d}): F1 {_fmt(sd['f1'], sd.get('f1_ci'))}{r5}")
    print("----------------------------------------")
    print(f"Full report saved to:\n  {output_path}")


if __name__ == "__main__":
    main()
