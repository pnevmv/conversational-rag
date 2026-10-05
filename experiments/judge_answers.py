"""Score generated answers with an LLM judge (src/evaluation/judge.py) instead of token F1 only.

Commands:
    run        judge result files (default: the dev-500 pipelines below) and write a summary
    export     sample answers for human labelling, to check the judge
    agreement  compare the human labels with the judge
    stability  compare two judge runs (--run-id) on the same answers

    python experiments/judge_answers.py run --workers 8
    python experiments/judge_answers.py run --limit 20            # quick check
    python experiments/judge_answers.py export --n 100
    python experiments/judge_answers.py agreement
    python experiments/judge_answers.py run --run-id run2 && python experiments/judge_answers.py stability --other run2

Judge calls are cached per model (and run id) in experiments/cache/judge/, so a rerun only
pays for new answers. Per-answer verdicts go to experiments/results/judge/<model>/ (not tracked).
"""
import argparse
import csv
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import bootstrap_ci, load_records, paired_bootstrap_test
from src.data.loader import load_qa_pairs, load_sections, make_section_id
from src.evaluation.judge import (DEFAULT_MODEL, SCORES, JudgeClient, build_prompt, format_history,
                                  parse_verdict, rule_verdict)
from src.evaluation.metrics import compute_metrics
from src.llm import LLMCache, generate_batch

DEV_DIR = PROJECT_ROOT / "experiments" / "results" / "dev_500"
OUT_ROOT = PROJECT_ROOT / "experiments" / "results" / "judge"
CACHE_ROOT = PROJECT_ROOT / "experiments" / "cache" / "judge"
HUMAN_CSV = OUT_ROOT / "human_labels.csv"
BASELINE = "rag_rewrite_rerank_v2"
DEFAULT_FILES = [
    "llm_baseline", "oracle_context_v2", "rag_rewrite_baseline_v2", "rag_rewrite_rerank_v2",
    "kg_sections", "kg_sections_1hop", "kg_facts", "kg_hybrid", "kg_rerank",
    "step4_plus_facts", "step4_plus_random_facts",
]
RETRY_SUFFIX = "\n\nReturn only the JSON object."


def slug(model: str) -> str:
    return model.replace("/", "_")


def load_context() -> Dict[str, Any]:
    examples = {ex["example_id"]: ex for ex in load_qa_pairs(split="validation", max_examples=None)}
    sections = {}
    for s in load_sections():
        sid = make_section_id(s["doc_id"], s["id_sp"])
        for sp in s["span_ids"]:
            sections[(s["doc_id"], str(sp))] = (sid, s)
    return {"examples": examples, "sections": sections}


def gold_text(example: Dict[str, Any], sections: Dict) -> str:
    seen, parts = set(), []
    for g in example.get("grounding") or []:
        hit = sections.get((g.get("doc_id"), str(g.get("id_sp"))))
        if hit and hit[0] not in seen:
            seen.add(hit[0])
            s = hit[1]
            parts.append(f"{s['title']}" + (f" - {s['section_title']}" if s.get("section_title") else "") + f"\n{s['text']}")
    return "\n\n".join(parts)


def judge_file(path: Path, client: JudgeClient, cache: LLMCache, ctx: Dict, workers: int,
               limit: Optional[int]) -> List[Dict[str, Any]]:
    records = load_records(path)[:limit] if limit else load_records(path)
    rows, prompts, pending = [], [], []
    for rec in records:
        ex = {**ctx["examples"].get(rec["example_id"], {}), **{k: rec[k] for k in
              ("question", "reference_answer", "is_unanswerable") if k in rec}}
        answer = rec.get("model_answer")
        row = {"example_id": rec["example_id"], "domain": rec.get("domain"),
               "is_unanswerable": rec.get("is_unanswerable", False),
               "is_doc_switch": rec.get("is_doc_switch", False),
               "recall_at_5": rec.get("recall_at_5"),
               "f1": compute_metrics(answer or "", rec["reference_answer"])["f1"],
               "question": rec["question"], "reference_answer": rec["reference_answer"], "answer": answer}
        verdict = rule_verdict(ex, answer)
        if verdict is None:
            pending.append(len(rows))
            prompts.append(build_prompt(ex, answer, gold_text(ex, ctx["sections"])))
        else:
            row.update(verdict)
        rows.append(row)

    replies = generate_batch(client, prompts, cache=cache, max_workers=workers, verbose=False)
    retry_idx, retry_prompts = [], []
    for i, prompt, (text, status) in zip(pending, prompts, replies):
        parsed = parse_verdict(text) if text else None
        if parsed:
            rows[i].update(parsed, by="judge")
        else:
            retry_idx.append(i)
            retry_prompts.append(prompt + RETRY_SUFFIX)
            rows[i]["error"] = status if text is None else "unparsed"
    if retry_prompts:
        for i, (text, status) in zip(retry_idx, generate_batch(client, retry_prompts, cache=cache,
                                                               max_workers=workers, verbose=False)):
            parsed = parse_verdict(text) if text else None
            if parsed:
                rows[i].pop("error", None)
                rows[i].update(parsed, by="judge")
            else:
                rows[i].update(verdict=None, by="judge", error=status if text is None else "unparsed")
    for r in rows:
        r["score"] = SCORES.get(r.get("verdict")) if r.get("verdict") else None
    return rows


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [r for r in rows if r["score"] is not None]

    def part(sub):
        if not sub:
            return {"n": 0}
        v = Counter(r["verdict"] for r in sub)
        judged = [r for r in sub if r.get("by") == "judge" and r.get("supported") is not None]
        return {"n": len(sub), "score": bootstrap_ci([r["score"] for r in sub]),
                "correct": v["correct"] / len(sub), "partial": v["partial"] / len(sub),
                "incorrect": v["incorrect"] / len(sub),
                "supported": (sum(r["supported"] for r in judged) / len(judged)) if judged else None,
                "f1": float(np.mean([r["f1"] for r in sub]))}
    return {"n_total": len(rows), "n_scored": len(ok), "n_failed": len(rows) - len(ok),
            "n_judge_calls": sum(1 for r in rows if r.get("by") == "judge"),
            "all": part(ok), "answerable": part([r for r in ok if not r["is_unanswerable"]]),
            "unanswerable": part([r for r in ok if r["is_unanswerable"]]),
            "doc_switch": part([r for r in ok if r["is_doc_switch"]])}


def cmd_run(args) -> None:
    client = JudgeClient(model=args.model)
    out_dir = OUT_ROOT / slug(client.model) / (args.run_id or "")
    cache = LLMCache(CACHE_ROOT / slug(client.model) / (args.run_id or "default"))
    ctx = load_context()
    files = [Path(f) for f in args.inputs] if args.inputs else [DEV_DIR / f"{n}.jsonl" for n in DEFAULT_FILES]
    files = [f for f in files if f.exists()]
    all_rows: Dict[str, List[Dict]] = {}
    for f in files:
        rows = judge_file(f, client, cache, ctx, args.workers, args.limit)
        all_rows[f.stem] = rows
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / f"{f.stem}.jsonl", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        s = summarise(rows)
        print(f"{f.stem:28} judge {s['all']['score']['mean']*100:5.1f}  correct {s['all']['correct']*100:5.1f}%  "
              f"F1 {s['all']['f1']*100:5.1f}  ({s['n_judge_calls']} judge calls, {s['n_failed']} failed)")

    summary = {"model": client.model, "run_id": args.run_id, "limit": args.limit,
               "files": {k: summarise(v) for k, v in all_rows.items()}, "paired_vs_baseline": {}}
    if BASELINE in all_rows:
        base = {r["example_id"]: r for r in all_rows[BASELINE]}
        for name, rows in all_rows.items():
            if name == BASELINE:
                continue
            pairs = [(r["score"], base[r["example_id"]]["score"]) for r in rows
                     if r["score"] is not None and r["example_id"] in base and base[r["example_id"]]["score"] is not None]
            if pairs:
                summary["paired_vs_baseline"][name] = paired_bootstrap_test([a for a, _ in pairs], [b for _, b in pairs])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary, out_dir / "summary.md")
    print(f"cache: {cache.stats}\nSummary -> {out_dir / 'summary.md'}")


def write_markdown(summary: Dict[str, Any], path: Path) -> None:
    def pct(x):
        return "-" if x is None else f"{x * 100:.1f}"
    lines = [f"# LLM judge: {summary['model']}" + (f" (run {summary['run_id']})" if summary["run_id"] else ""), "",
             "Score: correct = 1, partial = 0.5, incorrect = 0. Abstentions are scored by rule. "
             "ΔScore is the paired bootstrap difference to the Step 4 best.", "",
             "| Pipeline | n | Judge score [95% CI] | Correct | Partial | Supported | Answerable score | Unanswerable score | Token F1 | ΔScore vs Step 4 |",
             "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
    for name, s in summary["files"].items():
        a = s["all"]
        p = summary["paired_vs_baseline"].get(name)
        delta = f"{p['mean_diff']*100:+.1f} [{p['ci_low']*100:.1f}, {p['ci_high']*100:.1f}]" if p else "-"
        lines.append(f"| {name} | {a['n']} | {pct(a['score']['mean'])} [{pct(a['score']['ci_low'])}, {pct(a['score']['ci_high'])}] | "
                     f"{pct(a['correct'])} | {pct(a['partial'])} | {pct(a['supported'])} | "
                     f"{pct(s['answerable'].get('score', {}).get('mean'))} | {pct(s['unanswerable'].get('score', {}).get('mean'))} | "
                     f"{pct(a['f1'])} | {delta} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_export(args) -> None:
    """Random judged answers (answerable, not abstained), spread over the pipelines; the judge verdict is hidden."""
    judge_dir = OUT_ROOT / slug(args.model or _default_model())
    ctx = load_context()
    pool = []
    for f in sorted(judge_dir.glob("*.jsonl")):
        for r in map(json.loads, open(f, encoding="utf-8")):
            if r.get("by") == "judge" and r.get("verdict"):
                pool.append((f.stem, r))
    rng = random.Random(42)
    rng.shuffle(pool)
    sample = pool[:args.n]
    HUMAN_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(HUMAN_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "pipeline", "example_id", "history", "question", "reference_answer",
                    "gold_section", "answer", "label", "note"])
        for k, (pipe, r) in enumerate(sample, 1):
            ex = ctx["examples"][r["example_id"]]
            w.writerow([f"h{k:03d}", pipe, r["example_id"], format_history(ex.get("dialogue_history") or []),
                        r["question"], r["reference_answer"], gold_text(ex, ctx["sections"]), r["answer"], "", ""])
    print(f"{len(sample)} answers -> {HUMAN_CSV}\nFill `label` with correct / partial / incorrect.")


def _default_model() -> str:
    return os.getenv("JUDGE_MODEL") or DEFAULT_MODEL


def kappa(a: List[str], b: List[str]) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in labels) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def cmd_agreement(args) -> None:
    judge_dir = OUT_ROOT / slug(args.model or _default_model())
    verdicts = {}
    for f in judge_dir.glob("*.jsonl"):
        for r in map(json.loads, open(f, encoding="utf-8")):
            verdicts[(f.stem, r["example_id"])] = r.get("verdict")
    human, judge = [], []
    for row in csv.DictReader(open(HUMAN_CSV, encoding="utf-8")):
        label = row["label"].strip().lower()
        v = verdicts.get((row["pipeline"], row["example_id"]))
        if label in SCORES and v:
            human.append(label)
            judge.append(v)
    if not human:
        print("No labelled rows yet.")
        return
    n = len(human)
    exact = sum(h == j for h, j in zip(human, judge)) / n
    hb = ["correct" if h == "correct" else "not" for h in human]
    jb = ["correct" if j == "correct" else "not" for j in judge]
    print(f"{n} labelled answers")
    print(f"  exact agreement {exact:.1%}, Cohen's kappa {kappa(human, judge):.2f}")
    print(f"  correct vs not: agreement {sum(a == b for a, b in zip(hb, jb)) / n:.1%}, kappa {kappa(hb, jb):.2f}")
    print("  confusion (human -> judge):")
    for h in SCORES:
        print(f"    {h:9} " + "  ".join(f"{j} {sum(1 for x, y in zip(human, judge) if x == h and y == j)}" for j in SCORES))


def cmd_stability(args) -> None:
    base = OUT_ROOT / slug(args.model or _default_model())
    a_dir, b_dir = base, base / args.other
    a, b = [], []
    for f in b_dir.glob("*.jsonl"):
        other = {r["example_id"]: r for r in map(json.loads, open(f, encoding="utf-8"))}
        for r in map(json.loads, open(a_dir / f.name, encoding="utf-8")):
            o = other.get(r["example_id"])
            if o and r.get("by") == "judge" and r.get("verdict") and o.get("verdict"):
                a.append(r["verdict"])
                b.append(o["verdict"])
    if not a:
        print("Nothing to compare.")
        return
    print(f"{len(a)} judge verdicts: same verdict {sum(x == y for x, y in zip(a, b)) / len(a):.1%}, kappa {kappa(a, b):.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--inputs", nargs="+")
    p.add_argument("--model")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit", type=int, help="only the first N answers of each file")
    p.add_argument("--run-id", help="separate cache and output, for a stability check")
    p = sub.add_parser("export")
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--model")
    p = sub.add_parser("agreement")
    p.add_argument("--model")
    p = sub.add_parser("stability")
    p.add_argument("--other", required=True)
    p.add_argument("--model")
    args = parser.parse_args()
    {"run": cmd_run, "export": cmd_export, "agreement": cmd_agreement, "stability": cmd_stability}[args.cmd](args)


if __name__ == "__main__":
    main()
