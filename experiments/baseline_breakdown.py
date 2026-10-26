"""F1 of the LLM-only baseline and the oracle on all, answerable and unanswerable questions,
from the cached answers (no LLM calls), for the validation and the test split.

    python experiments/baseline_breakdown.py

Writes experiments/results/<split>/baselines_by_answerability.json and .md.
"""
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.metrics import compute_metrics, is_abstention

SYSTEMS = {"llm_baseline": "LLM only", "oracle_context_v2": "Oracle (gold sections)"}


def main() -> None:
    for split in ("validation", "test"):
        res_dir = PROJECT_ROOT / "experiments" / "results" / split
        out = {}
        lines = [f"# LLM only and oracle by answerability ({split})", "",
                 "Token F1 (%) from the cached answers; questions without an answer (API error) are left out. "
                 "Abstention: share of unanswerable questions where the model abstains / share of answerable "
                 "questions where it abstains.", "",
                 "| System | n | F1 all | F1 answerable | F1 unanswerable | abstain recall / false abstention |",
                 "| :--- | ---: | :---: | :---: | :---: | :---: |"]
        for name, label in SYSTEMS.items():
            rows = [json.loads(l) for l in open(res_dir / f"{name}.jsonl", encoding="utf-8")]
            rows = [r for r in rows if r["model_answer"] is not None]
            f = np.array([compute_metrics(r["model_answer"], r["reference_answer"])["f1"] for r in rows])
            u = np.array([r["is_unanswerable"] for r in rows])
            ab = np.array([is_abstention(r["model_answer"]) for r in rows])
            out[name] = {"n": len(rows), "n_unanswerable": int(u.sum()), "f1": float(f.mean()),
                         "f1_answerable": float(f[~u].mean()), "f1_unanswerable": float(f[u].mean()),
                         "abstain_recall": float(ab[u].mean()), "false_abstention": float(ab[~u].mean())}
            e = out[name]
            lines.append(f"| {label} | {e['n']} | {e['f1']*100:.1f} | {e['f1_answerable']*100:.1f} | "
                         f"{e['f1_unanswerable']*100:.1f} | {e['abstain_recall']*100:.1f} / {e['false_abstention']*100:.1f} |")
        (res_dir / "baselines_by_answerability.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        (res_dir / "baselines_by_answerability.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
