import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.metrics import compute_metrics

DEFAULT_INPUT = PROJECT_ROOT / "experiments" / "results" / "llm_baseline.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments" / "results" / "llm_baseline_evaluation.json"


def evaluate(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
) -> Dict[str, Any]:
    """
    Evaluate baseline predictions against reference answers.

    Reads a JSONL file produced by llm_baseline.py, computes Exact Match and
    token-level F1 for each example that has a model_answer, and writes a
    JSON report with per-example scores and aggregate statistics.
    """
    records: List[Dict[str, Any]] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    results: List[Dict[str, Any]] = []
    skipped = 0

    for rec in records:
        if rec.get("status") != "success" or rec.get("model_answer") is None:
            skipped += 1
            continue

        scores = compute_metrics(
            prediction=rec["model_answer"],
            reference=rec["reference_answer"],
        )

        results.append({
            "example_id": rec["example_id"],
            "domain": rec["domain"],
            "question": rec["question"],
            "reference_answer": rec["reference_answer"],
            "model_answer": rec["model_answer"],
            "exact_match": scores["exact_match"],
            "f1": scores["f1"],
        })

    n = len(results)
    if n == 0:
        aggregate = {"exact_match": 0.0, "f1": 0.0}
    else:
        aggregate = {
            "exact_match": sum(r["exact_match"] for r in results) / n,
            "f1": sum(r["f1"] for r in results) / n,
        }

    report = {
        "experiment": "llm_baseline",
        "input_file": str(input_path),
        "total_examples": len(records),
        "evaluated": n,
        "skipped": skipped,
        "aggregate": aggregate,
        "per_example": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate experiment predictions.")
    parser.add_argument("--input", type=str, default=None, help="Path to predictions JSONL")
    parser.add_argument("--output", type=str, default=None, help="Path to save evaluation JSON")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else DEFAULT_INPUT
    output_path = Path(args.output) if args.output else (
        input_path.parent / (input_path.stem + "_evaluation.json")
    )

    report = evaluate(input_path=input_path, output_path=output_path)

    agg = report["aggregate"]
    print("----------------------------------------")
    print(f"Evaluated : {report['evaluated']} / {report['total_examples']}")
    print(f"Skipped   : {report['skipped']}")
    print(f"Exact Match: {agg['exact_match']:.4f}  ({agg['exact_match']*100:.2f}%)")
    print(f"Token F1   : {agg['f1']:.4f}  ({agg['f1']*100:.2f}%)")
    print("----------------------------------------")
    print(f"Full report saved to:\n  {output_path}")


if __name__ == "__main__":
    main()
