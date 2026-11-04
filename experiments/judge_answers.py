"""Score the answers of the systems on dev-500 with an LLM judge (src/evaluation/judge.py, gpt-6-luna).

Token F1 only counts word overlap with the reference, so correct paraphrases get low scores. The
judge re-scores the cached answers; nothing is generated again. Systems (dev-500 of the validation
split, data/dev_500_ids.json):

    llm      no documents (G0 prompt)
    oracle   gold section given (G0 prompt)
    p        passages, G2 + abstain(G0)
    e        passages + 30 one-hop facts, G2 + abstain(G0) (final system)
    e_cite   E with citations (the baseline of the agents; citations stripped before judging)
    v1       passages + top 10 facts by cross-encoder, G2 + abstain(G0)
    a1       A1 agent, abstain(G0)          a1_own  A1 with its own refusal
    a2       A2 agent, abstain(G0)          a2_own  A2 with its own refusal

Commands:
    cost       count the tokens of every judge call (no API calls) and estimate the cost
    run        judge the systems and write a summary (paired difference to E)
    export     sample 60 answers of P, E and V1 for human labelling (half random, half where judge and F1
               disagree most)
    carry      copy labels of an earlier sample onto the same answers in the current one
    agreement  compare the human labels with the judge (kappa for 3 classes and two binary splits)
    stability  compare two judge runs (--run-id) on the same answers

    python experiments/judge_answers.py cost
    python experiments/judge_answers.py run --limit 20            # quick check
    python experiments/judge_answers.py run --workers 8
    python experiments/judge_answers.py export
    python experiments/judge_answers.py carry --from my_labels.csv
    python experiments/judge_answers.py agreement
    python experiments/judge_answers.py run --run-id run2 && python experiments/judge_answers.py stability --other run2
    python experiments/judge_answers.py cost --split test        # final P, E, V1 on a whole split
    python experiments/judge_answers.py run --split validation

Judge calls are cached per model (and run id) in experiments/cache/judge/, so a rerun only pays
for new answers. Per-answer verdicts and the summary go to experiments/results/judge/<model>/dev_500/.
"""
import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import bootstrap_ci, paired_bootstrap_test
from src.data.loader import load_qa_pairs, load_sections, make_section_id
from src.evaluation.judge import (DEFAULT_MODEL, SCORES, JudgeClient, build_prompt, format_history,
                                  parse_verdict, rule_verdict)
from src.evaluation.metrics import compute_metrics, is_abstention
from src.llm import LLMCache, call_meta, generate_batch

VAL = PROJECT_ROOT / "experiments" / "results" / "validation"
GEN = VAL / "generator_input"
AGENT = PROJECT_ROOT / "experiments" / "results" / "dev_500" / "agent"
DEV_IDS = PROJECT_ROOT / "data" / "dev_500_ids.json"
OUT_ROOT = PROJECT_ROOT / "experiments" / "results" / "judge"
CACHE_ROOT = PROJECT_ROOT / "experiments" / "cache" / "judge"
TEST_STEP7 = PROJECT_ROOT / "experiments" / "results" / "test" / "step7"
SUBSET = "dev_500"
# Output folder per split. On the full validation and test splits only the final systems are judged.
SPLITS = {"dev500": "dev_500", "validation": "validation", "test": "test"}
FULL_SYSTEMS = ("p", "e", "v1")
COMPARISONS = (("v1", "p"), ("e", "p"), ("v1", "e"))  # as in experiments/results/test/step7_final.md
BASELINE = "e"
ABSTAIN = "Unfortunately, no relevant information is found."
RETRY_SUFFIX = "\n\nReturn only the JSON object."
# USD per 1M tokens of gpt-6-luna, from experiments/model_comparison.py (Azure Retail Prices API, 2026-10-21).
PRICE = {"input": 0.10, "cached_input": 0.01, "output": 0.50}
# Output tokens per judge call (JSON reply + reasoning) for the cost estimate: gpt-6-luna used 89 on
# average as a generator (47 of them reasoning), the judge reply is about 50 tokens before reasoning.
OUTPUT_SCENARIOS = (100, 300, 600)
REQUEST_OVERHEAD = 10  # tokens the API adds around one user message


def slug(model: str) -> str:
    return model.replace("/", "_")


def load(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def by_id(path: Path) -> Dict[str, Dict[str, Any]]:
    return {r["example_id"]: r for r in load(path)}


def strip_citations(answer: Optional[str]) -> Optional[str]:
    from experiments.sources import strip_citations as strip
    return None if answer is None else strip(answer)


# ---------------------------------------------------------------------------- systems
# Each loader returns {example_id: (answer, context, context_known)}; answers may be None (failed call).
Answers = Dict[str, Tuple[Optional[str], Optional[str], bool]]


def _single(name: str) -> Answers:
    return {i: (r["model_answer"], r.get("context"), True) for i, r in by_id(VAL / f"{name}.jsonl").items()}


def _g2_abstain_g0(pipeline: str, split: str = "dev500") -> Answers:
    """G2 + abstain(G0), as in experiments/sources.py: abstain if G0 abstains, else the G2 answer.
    On the test split the answers come composed from the Step 7 run."""
    if split == "test":
        name = {"rag_rewrite_rerank_v2": "p", "step4_plus_facts": "e"}[pipeline]
        return {i: (r["model_answer"], r["context"], True) for i, r in by_id(TEST_STEP7 / f"{name}.jsonl").items()}
    g0, g2 = by_id(GEN / f"{pipeline}__G0.jsonl"), by_id(GEN / f"{pipeline}__G2_kall.jsonl")
    ctx = by_id(VAL / f"{pipeline}.jsonl")
    out = {}
    for i, r in g0.items():
        a0 = r["model_answer"]
        ans = None if a0 is None else (ABSTAIN if is_abstention(a0) else g2[i]["model_answer"])
        out[i] = (ans, ctx[i]["context"], True)
    return out


def _cite() -> Answers:
    ctx = by_id(VAL / "step4_plus_facts.jsonl")
    return {i: (strip_citations(r["model_answer"]), ctx[i]["context"], True)
            for i, r in by_id(VAL / "sources" / "cite_validation.jsonl").items()}


def _v1(split: str = "dev500") -> Answers:
    path = TEST_STEP7 / "v1_k10.jsonl" if split == "test" else VAL / "graph_rag" / "v1_k10.jsonl"
    return {i: (r["model_answer"], r["context"], True) for i, r in by_id(path).items()}


def _agent(file: str, field: str) -> Answers:
    # The agents' extended contexts are not stored: "supported" is judged against the gold section only.
    return {i: (strip_citations(r.get(field)), None, False) for i, r in by_id(AGENT / file).items()}


# Loaders take the split; only P, E and V1 exist beyond dev-500 (FULL_SYSTEMS).
SYSTEMS: Dict[str, Tuple[str, Callable[[str], Answers]]] = {
    "llm": ("LLM only, no documents", lambda split: _single("llm_baseline")),
    "oracle": ("Gold section given", lambda split: _single("oracle_context_v2")),
    "p": ("P: passages", lambda split: _g2_abstain_g0("rag_rewrite_rerank_v2", split)),
    "e": ("E: passages + 30 facts", lambda split: _g2_abstain_g0("step4_plus_facts", split)),
    "e_cite": ("E with citations", lambda split: _cite()),
    "v1": ("V1: passages + 10 facts", _v1),
    "a1": ("A1 agent, abstain(G0)", lambda split: _agent("a1.jsonl", "a1_g0")),
    "a1_own": ("A1 agent, own refusal", lambda split: _agent("a1.jsonl", "a1_own")),
    "a2": ("A2 agent, abstain(G0)", lambda split: _agent("a2.jsonl", "a2_g0")),
    "a2_own": ("A2 agent, own refusal", lambda split: _agent("a2.jsonl", "a2_own")),
}


def load_context(split: str = "dev500") -> Dict[str, Any]:
    qa = load_qa_pairs(split="test" if split == "test" else "validation", max_examples=None)
    examples = {ex["example_id"]: ex for ex in qa}
    ids = json.load(open(DEV_IDS, encoding="utf-8")) if split == "dev500" else [ex["example_id"] for ex in qa]
    sections = {}
    for s in load_sections():
        sid = make_section_id(s["doc_id"], s["id_sp"])
        for sp in s["span_ids"]:
            sections[(s["doc_id"], str(sp))] = (sid, s)
    return {"split": split, "ids": ids, "examples": examples, "sections": sections}


def gold_text(example: Dict[str, Any], sections: Dict) -> str:
    seen, parts = set(), []
    for g in example.get("grounding") or []:
        hit = sections.get((g.get("doc_id"), str(g.get("id_sp"))))
        if hit and hit[0] not in seen:
            seen.add(hit[0])
            s = hit[1]
            parts.append(f"{s['title']}" + (f" - {s['section_title']}" if s.get("section_title") else "") + f"\n{s['text']}")
    return "\n\n".join(parts)


def prepare(system: str, ctx: Dict, limit: Optional[int]) -> Tuple[List[Dict], List[int], List[str], List[Dict]]:
    """Rows of one system on the split of ctx; rule verdicts filled in, prompts for the rest."""
    answers = SYSTEMS[system][1](ctx["split"])
    ids = ctx["ids"][:limit] if limit else ctx["ids"]
    rows, pending, prompts, metas = [], [], [], []
    for i in ids:
        ex = ctx["examples"][i]
        answer, context, known = answers[i]
        row = {"example_id": i, "domain": ex.get("domain"), "is_unanswerable": bool(ex.get("is_unanswerable")),
               "is_doc_switch": bool(ex.get("is_doc_switch")),
               "f1": compute_metrics(answer or "", ex["reference_answer"])["f1"],
               "question": ex["question"], "reference_answer": ex["reference_answer"], "answer": answer}
        if answer is None:
            row.update(verdict=None, by="missing", error="no answer from the system")
        else:
            verdict = rule_verdict(ex, answer)
            if verdict is None:
                pending.append(len(rows))
                prompts.append(build_prompt(ex, answer, gold_text(ex, ctx["sections"]), context, known))
                metas.append(call_meta(ex, "judge", pipeline=system))
            else:
                row.update(verdict)
        rows.append(row)
    return rows, pending, prompts, metas


def judge_system(system: str, client: JudgeClient, cache: LLMCache, ctx: Dict, workers: int,
                 limit: Optional[int]) -> List[Dict[str, Any]]:
    rows, pending, prompts, metas = prepare(system, ctx, limit)
    replies = generate_batch(client, prompts, cache=cache, max_workers=workers, verbose=False, metas=metas)
    retry = []
    for i, prompt, meta, (text, status) in zip(pending, prompts, metas, replies):
        parsed = parse_verdict(text) if text else None
        if parsed:
            rows[i].update(parsed, by="judge")
        else:
            retry.append((i, prompt + RETRY_SUFFIX, meta))
            rows[i]["error"] = status if text is None else "unparsed"
    if retry:
        again = generate_batch(client, [p for _, p, _ in retry], cache=cache, max_workers=workers, verbose=False,
                               metas=[m for _, _, m in retry])
        for (i, _, _), (text, status) in zip(retry, again):
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
    failed = Counter("content filter" if "content management policy" in (r.get("error") or "") else (r.get("error") or "")[:80]
                     for r in rows if r["score"] is None)
    return {"n_total": len(rows), "n_scored": len(ok), "n_failed": len(rows) - len(ok), "failed": dict(failed),
            "n_judge_calls": sum(1 for r in rows if r.get("by") == "judge"),
            "all": part(ok), "answerable": part([r for r in ok if not r["is_unanswerable"]]),
            "unanswerable": part([r for r in ok if r["is_unanswerable"]]),
            "doc_switch": part([r for r in ok if r["is_doc_switch"]])}


def out_dir(model: str, run_id: Optional[str], split: str = "dev500") -> Path:
    return OUT_ROOT / slug(model) / SPLITS[split] / (run_id or "")


def systems_for(args) -> List[str]:
    if args.split == "dev500":
        return args.systems or list(SYSTEMS)
    bad = [x for x in (args.systems or []) if x not in FULL_SYSTEMS]
    if bad:
        raise SystemExit(f"only {', '.join(FULL_SYSTEMS)} exist on the {args.split} split, not {', '.join(bad)}")
    return args.systems or list(FULL_SYSTEMS)


def cache_for(model: str, run_id: Optional[str]) -> LLMCache:
    return LLMCache(CACHE_ROOT / slug(model) / (run_id or "default"))


# ---------------------------------------------------------------------------- commands
def cmd_cost(args) -> None:
    """Token count of every judge call that is not cached yet, and the cost at the gpt-6-luna price."""
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    model = args.model or _default_model()
    cache = cache_for(model, args.run_id)
    ctx = load_context(args.split)
    systems = systems_for(args)
    seen, lines, total_in, total_calls = set(), [], 0, 0
    lines.append(f"Judge {model}, {SPLITS[args.split]}" + (f", first {args.limit} questions" if args.limit else "") +
                 f"; price USD {PRICE['input']:.2f} input / {PRICE['output']:.2f} output per 1M tokens")
    lines.append(f"{'system':8} {'answers':>7} {'by rule':>7} {'calls':>6} {'input tok':>10} {'tok/call':>8}")
    for name in systems:
        rows, pending, prompts, _ = prepare(name, ctx, args.limit)
        new = [p for p in dict.fromkeys(prompts) if p not in seen and cache.get_entry(p) is None]
        seen.update(prompts)
        n_in = sum(len(enc.encode(p, disallowed_special=())) + REQUEST_OVERHEAD for p in new)
        total_in += n_in
        total_calls += len(new)
        n_rule = sum(1 for r in rows if r.get("by") == "rule")
        lines.append(f"{name:8} {len(rows):7} {n_rule:7} {len(new):6} {n_in:10,} {n_in / max(1, len(new)):8,.0f}")
    lines.append(f"{'total':8} {'':7} {'':7} {total_calls:6} {total_in:10,}")
    in_cost = total_in * PRICE["input"] / 1e6
    for out_tok in OUTPUT_SCENARIOS:
        out_cost = total_calls * out_tok * PRICE["output"] / 1e6
        lines.append(f"  {out_tok:3} output tokens per call: USD {in_cost:.2f} input + {out_cost:.2f} output "
                     f"= {in_cost + out_cost:.2f}")
    lines.append("Retries after an unparsed reply and a second run for --run-id are not included.")
    print("\n".join(lines))


def cmd_run(args) -> None:
    client = JudgeClient(model=args.model)
    out = out_dir(client.model, args.run_id, args.split)
    cache = cache_for(client.model, args.run_id)
    ctx = load_context(args.split)
    all_rows: Dict[str, List[Dict]] = {}
    for name in systems_for(args):
        rows = judge_system(name, client, cache, ctx, args.workers, args.limit)
        all_rows[name] = rows
        out.mkdir(parents=True, exist_ok=True)
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        s = summarise(rows)
        if not s["n_scored"]:
            errors = Counter((r.get("error") or "")[:120] for r in rows if r["score"] is None)
            print(f"{name:8} no verdicts ({s['n_failed']} failed): {errors.most_common(1)[0][0]}")
            continue
        print(f"{name:8} judge {s['all']['score']['mean']*100:5.1f}  correct {s['all']['correct']*100:5.1f}%  "
              f"F1 {s['all']['f1']*100:5.1f}  ({s['n_judge_calls']} judge calls, {s['n_failed']} failed)", flush=True)

    summary = {"model": client.model, "deployment": client.default_model, "subset": SPLITS[args.split],
               "run_id": args.run_id, "limit": args.limit,
               "systems": {k: {"label": SYSTEMS[k][0], **summarise(v)} for k, v in all_rows.items()
                           if summarise(v)["n_scored"]},
               "paired_vs_e": {}}
    if args.split != "dev500":
        summary.pop("paired_vs_e")
        summary["paired"] = paired_comparisons(all_rows)
    elif BASELINE in all_rows:
        base = {r["example_id"]: r["score"] for r in all_rows[BASELINE]}
        for name, rows in all_rows.items():
            if name == BASELINE:
                continue
            for part, keep in (("all", lambda r: True), ("answerable", lambda r: not r["is_unanswerable"])):
                pairs = [(r["score"], base[r["example_id"]]) for r in rows if keep(r)
                         and r["score"] is not None and base.get(r["example_id"]) is not None]
                if pairs:
                    summary["paired_vs_e"].setdefault(name, {})[part] = paired_bootstrap_test(
                        [a for a, _ in pairs], [b for _, b in pairs])
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (write_markdown if args.split == "dev500" else write_markdown_full)(summary, out / "summary.md")
    print(f"cache: {cache.stats}\nSummary -> {out / 'summary.md'}")


def paired_comparisons(all_rows: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Paired bootstrap differences of judge score and token F1 for COMPARISONS, on all / answerable /
    unanswerable questions; questions without a verdict from either system are left out."""
    out = {}
    for a, b in COMPARISONS:
        if a not in all_rows or b not in all_rows:
            continue
        rb = {r["example_id"]: r for r in all_rows[b]}
        both = [(r, rb[r["example_id"]]) for r in all_rows[a]
                if r["score"] is not None and rb.get(r["example_id"], {}).get("score") is not None]
        res = {"n": len(both)}
        for part, keep in (("all", lambda r: True), ("answerable", lambda r: not r["is_unanswerable"]),
                           ("unanswerable", lambda r: r["is_unanswerable"])):
            sub = [(x, y) for x, y in both if keep(x)]
            if sub:
                res[part] = {m: paired_bootstrap_test([x[m] for x, _ in sub], [y[m] for _, y in sub])
                             for m in ("score", "f1")}
        out[f"{a} vs {b}"] = res
    return out


def failed_note(summary: Dict[str, Any]) -> str:
    """Sentence on questions without a verdict, which the paired differences leave out."""
    parts = [f"{s['label'].split(':')[0]} {s['n_failed']} ({', '.join(s['failed'])})"
             for s in summary["systems"].values() if s.get("n_failed")]
    return (" Questions without a verdict, left out: " + "; ".join(parts) + ".") if parts else ""


def write_markdown_full(summary: Dict[str, Any], path: Path) -> None:
    """Summary of the final systems on a whole split: judge score next to token F1, and paired differences."""
    def pct(x):
        return "-" if x is None else f"{x * 100:.1f}"

    def delta(p):
        return f"{p['mean_diff']*100:+.1f} [{p['ci_low']*100:.1f}, {p['ci_high']*100:.1f}]" if p else "-"
    n_un = next(iter(summary["systems"].values()))["unanswerable"].get("n", 0)
    lines = [f"# LLM judge: {summary['model']}, {summary['subset']} split" + (f" (run {summary['run_id']})" if summary["run_id"] else ""), "",
             "Final systems, evaluation only (nothing is re-selected). Score: correct = 1, partial = 0.5, incorrect = 0; "
             "abstentions are scored by rule. The judge (gpt-6-luna) is from the same model family as the generator "
             "(gpt-5.4-nano). Δ: paired bootstrap difference with its 95% interval. "
             f"{n_un} of the questions are unanswerable." + failed_note(summary), "",
             "| System | n | Judge score [95% CI] | Correct | Partial | Supported | Judge answerable | Judge unanswerable | Token F1 | F1 answerable |",
             "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
    for s in summary["systems"].values():
        a = s["all"]
        lines.append(f"| {s['label']} | {a['n']} | {pct(a['score']['mean'])} [{pct(a['score']['ci_low'])}, {pct(a['score']['ci_high'])}] | "
                     f"{pct(a['correct'])} | {pct(a['partial'])} | {pct(a['supported'])} | "
                     f"{pct(s['answerable'].get('score', {}).get('mean'))} | {pct(s['unanswerable'].get('score', {}).get('mean'))} | "
                     f"{pct(a['f1'])} | {pct(s['answerable'].get('f1'))} |")
    lines += ["", "| Comparison | n | Δ judge all | Δ judge answerable | Δ judge unanswerable | Δ F1 all | Δ F1 answerable | Δ F1 unanswerable |",
              "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
    for name, c in summary["paired"].items():
        a, b = (x.upper() for x in name.split(" vs "))
        cells = [delta(c.get(part, {}).get(m)) for m in ("score", "f1") for part in ("all", "answerable", "unanswerable")]
        lines.append(f"| {a} vs {b} | {c['n']} | " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(summary: Dict[str, Any], path: Path) -> None:
    def pct(x):
        return "-" if x is None else f"{x * 100:.1f}"

    def delta(p):
        return f"{p['mean_diff']*100:+.1f} [{p['ci_low']*100:.1f}, {p['ci_high']*100:.1f}]" if p else "-"
    lines = [f"# LLM judge: {summary['model']}, {summary['subset']}" + (f" (run {summary['run_id']})" if summary["run_id"] else ""), "",
             "Score: correct = 1, partial = 0.5, incorrect = 0. Abstentions are scored by rule. "
             "Supported: share of judged answers backed by the gold section or the context (agents: gold section only). "
             "Δ: paired bootstrap difference of the judge score to E, with its 95% interval.", "",
             "| System | n | Judge score [95% CI] | Correct | Partial | Supported | Answerable | Unanswerable | Token F1 | Δ all vs E | Δ answerable vs E |",
             "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
    for name, s in summary["systems"].items():
        a = s["all"]
        p = summary["paired_vs_e"].get(name, {})
        lines.append(f"| {s['label']} | {a['n']} | {pct(a['score']['mean'])} [{pct(a['score']['ci_low'])}, {pct(a['score']['ci_high'])}] | "
                     f"{pct(a['correct'])} | {pct(a['partial'])} | {pct(a['supported'])} | "
                     f"{pct(s['answerable'].get('score', {}).get('mean'))} | {pct(s['unanswerable'].get('score', {}).get('mean'))} | "
                     f"{pct(a['f1'])} | {delta(p.get('all'))} | {delta(p.get('answerable'))} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


HUMAN_SYSTEMS = ("p", "e", "v1")   # the systems the judge is applied to beyond dev-500
HUMAN_N = 60
HUMAN_N_EXTREME = 15          # per disagreement group
HUMAN_EXTREME_POOL = 3        # draw them from the 3 * 15 most extreme answers of the group
# Labels may also be written as scores.
LABEL_ALIASES = {"1": "correct", "0.5": "partial", "0": "incorrect"}


def norm_label(label: str) -> str:
    label = (label or "").strip().lower()
    return LABEL_ALIASES.get(label, label)


def human_paths(judge_dir: Path) -> Dict[str, Path]:
    return {"csv": judge_dir / "human_labels.csv", "md": judge_dir / "human_labels.md",
            "key": judge_dir / "human_labels_key.json"}


def cmd_export(args) -> None:
    """Answers for human labelling, with the judge verdict and the system hidden.

    Half are drawn at random from all judged answers; the other half are where the judge and token F1
    disagree most: judged incorrect with the highest F1, and judged correct with the lowest F1. Each
    distinct (question, answer) is labelled once. The strata and systems are kept in a separate key file.
    Answers come from P, E and V1 only (--systems).
    """
    judge_dir = out_dir(args.model or _default_model(), None)
    paths = human_paths(judge_dir)
    if paths["csv"].exists() and not args.force:
        filled = [r for r in csv.DictReader(open(paths["csv"], encoding="utf-8")) if r["label"].strip()]
        if filled:
            raise SystemExit(f"{paths['csv']} already has {len(filled)} labels; use --force to overwrite")
    ctx = load_context()
    pool, seen = [], set()
    for name in args.systems:
        f = judge_dir / f"{name}.jsonl"
        if not f.exists():
            continue
        for r in map(json.loads, open(f, encoding="utf-8")):
            key = (r["example_id"], (r.get("answer") or "").strip())
            if r.get("by") == "judge" and r.get("verdict") and key not in seen:
                seen.add(key)
                pool.append({**r, "system": name})
    rng = random.Random(args.seed)
    rng.shuffle(pool)
    k = args.n_extreme
    high_f1_wrong = sorted((r for r in pool if r["verdict"] == "incorrect"), key=lambda r: -r["f1"])
    low_f1_right = sorted((r for r in pool if r["verdict"] == "correct"), key=lambda r: r["f1"])
    picked = ([dict(r, stratum="high F1, judged incorrect") for r in rng.sample(high_f1_wrong[:HUMAN_EXTREME_POOL * k], k)] +
              [dict(r, stratum="low F1, judged correct") for r in rng.sample(low_f1_right[:HUMAN_EXTREME_POOL * k], k)])
    taken = {(r["example_id"], r["answer"]) for r in picked}
    rest = [r for r in pool if (r["example_id"], r["answer"]) not in taken]
    picked += [dict(r, stratum="random") for r in rng.sample(rest, args.n - len(picked))]
    rng.shuffle(picked)

    key, md = {}, ["# Human check of the LLM judge", "",
                   "Label each answer in `human_labels.csv` (column `label`: correct / partial / incorrect, or 1 / 0.5 / 0), with the "
                   "same rules as the judge: correct = gives the key information of the reference (wording and length "
                   "may differ, correct extra details are fine); partial = right topic but misses an important part or "
                   "adds a wrong detail; incorrect = something else, misses the point, refuses although the information "
                   "is available, or contradicts the document. If the reference is a clarifying question, a relevant "
                   "clarifying question or correct information on that topic is correct. The history shows the last four "
                   "turns, as the judge sees them.", ""]
    with open(paths["csv"], "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "example_id", "history", "question", "reference_answer", "gold_section", "answer",
                    "label", "note"])
        for n, r in enumerate(picked, 1):
            item = f"h{n:03d}"
            ex = ctx["examples"][r["example_id"]]
            hist, gold = format_history(ex.get("dialogue_history") or []), gold_text(ex, ctx["sections"])
            w.writerow([item, r["example_id"], hist, r["question"], r["reference_answer"], gold, r["answer"], "", ""])
            key[item] = {"system": r["system"], "example_id": r["example_id"], "stratum": r["stratum"], "f1": r["f1"]}
            md += [f"## {item}", "", "**History**", "", "```", hist, "```", "", f"**Question.** {r['question']}", "",
                   f"**Reference.** {r['reference_answer']}", "", f"**Answer.** {r['answer']}", "",
                   "<details><summary>Gold section</summary>", "", gold, "", "</details>", ""]
    paths["md"].write_text("\n".join(md), encoding="utf-8")
    paths["key"].write_text(json.dumps({"seed": args.seed, "systems": args.systems, "items": key}, indent=2),
                            encoding="utf-8")
    print(f"{len(picked)} answers ({Counter(r['stratum'] for r in picked)}) from {len(pool)} distinct judged answers")
    print(f"label: {paths['csv']}\nread:  {paths['md']}\nkey (do not open before labelling): {paths['key']}")


def _default_model() -> str:
    return os.getenv("JUDGE_MODEL") or DEFAULT_MODEL


def kappa(a: List[str], b: List[str]) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in labels) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def cmd_carry(args) -> None:
    """Copy labels of an earlier sample onto the same (question, answer) in the current one."""
    judge_dir = out_dir(args.model or _default_model(), None)
    paths = human_paths(judge_dir)
    old = {r["item_id"]: r for r in csv.DictReader(open(args.old, encoding="utf-8"))}
    given = list(csv.DictReader(open(args.from_csv, encoding="utf-8")))
    labels = {}
    for r in given:
        label = norm_label(r.get("label"))
        if not label:
            continue
        if label not in SCORES:
            print(f"skipped {r.get('item_id')}: label {r.get('label')!r} is not correct / partial / incorrect")
            continue
        src = r if r.get("example_id") and r.get("answer") else old.get(r.get("item_id"))
        if not src:
            print(f"skipped {r.get('item_id')}: not in {args.old}")
            continue
        labels[(src["example_id"], src["answer"].strip())] = (label, r.get("item_id"), r.get("note", "").strip())
    rows = list(csv.DictReader(open(paths["csv"], encoding="utf-8")))
    carried = []
    for r in rows:
        hit = labels.get((r["example_id"], r["answer"].strip()))
        if hit and not r["label"].strip():
            r["label"] = hit[0]
            r["note"] = "; ".join(x for x in (hit[2], f"carried from {hit[1]} of {Path(args.old).name}") if x)
            carried.append(f"{hit[1]} -> {r['item_id']} ({hit[0]})")
    with open(paths["csv"], "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(labels)} labels given, {len(carried)} carried over" + ("".join(f"\n  {c}" for c in carried)))


SCHEMES = {
    "3 classes": lambda x: x,
    "correct vs not": lambda x: "correct" if x == "correct" else "not",
    "correct+partial vs incorrect": lambda x: "incorrect" if x == "incorrect" else "correct+partial",
}


def cmd_agreement(args) -> None:
    """Human labels against the judge: agreement and Cohen's kappa for 3 classes and two binary splits,
    overall, on the random half and on the disagreement half."""
    base_dir = out_dir(args.model or _default_model(), None)
    paths = human_paths(base_dir)
    key = json.loads(paths["key"].read_text(encoding="utf-8"))["items"]
    raw = {r["item_id"]: r["label"] for r in csv.DictReader(open(paths["csv"], encoding="utf-8"))}
    bad = sorted(i for i, l in raw.items() if l.strip() and norm_label(l) not in SCORES)
    if bad:
        print(f"ignored, label not correct / partial / incorrect: {', '.join(bad)}")
    labels = {i: norm_label(l) for i, l in raw.items() if norm_label(l) in SCORES}
    if not labels:
        print("No labelled rows yet.")
        return
    halves = {"all": lambda s: True, "random": lambda s: s == "random", "disagreement": lambda s: s != "random"}
    model = args.model or _default_model()
    verdicts = {}
    for f in base_dir.glob("*.jsonl"):
        for r in map(json.loads, open(f, encoding="utf-8")):
            verdicts[(f.stem, r["example_id"])] = r.get("verdict")
    result = {"model": model, "n_items": len(key), "n_labelled": len(labels), "halves": {}}
    print(f"{model}: {len(labels)} of {len(key)} items labelled")
    for name, keep in halves.items():
        pairs = [(labels[i], verdicts.get((key[i]["system"], key[i]["example_id"]))) for i in labels
                 if keep(key[i]["stratum"])]
        pairs = [(h, j) for h, j in pairs if j]
        if not pairs:
            continue
        res = {"n": len(pairs),
               "confusion": {x: {y: sum(1 for a, b in pairs if a == x and b == y) for y in SCORES} for x in SCORES}}
        line = []
        for scheme, f in SCHEMES.items():
            h, j = [f(a) for a, _ in pairs], [f(b) for _, b in pairs]
            agree = sum(a == b for a, b in zip(h, j)) / len(pairs)
            k = kappa(h, j)
            res[scheme] = {"agreement": agree, "kappa": k}
            line.append(f"{scheme}: {agree:.0%}, kappa {k:.2f}")
        result["halves"][name] = res
        print(f"  {name:12} n {len(pairs):2}  " + "  |  ".join(line))
    if "all" in result["halves"]:
        print("  confusion, all (human -> judge):")
        for x in SCORES:
            print(f"    {x:9} " + "  ".join(f"{y} {result['halves']['all']['confusion'][x][y]}" for y in SCORES))
    (base_dir / "human_agreement.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"-> {base_dir / 'human_agreement.json'}")


def cmd_stability(args) -> None:
    model = args.model or _default_model()
    a_dir, b_dir = out_dir(model, None), out_dir(model, args.other)
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
    for name in ("cost", "run"):
        p = sub.add_parser(name)
        p.add_argument("--split", choices=list(SPLITS), default="dev500",
                       help="dev500 (all systems) or the whole validation / test split (P, E, V1 only)")
        p.add_argument("--systems", nargs="+", choices=list(SYSTEMS))
        p.add_argument("--model")
        p.add_argument("--limit", type=int, help="only the first N dev-500 questions")
        p.add_argument("--run-id", help="separate cache and output, for a stability check")
        if name == "run":
            p.add_argument("--workers", type=int, default=8)
    p = sub.add_parser("export")
    p.add_argument("--n", type=int, default=HUMAN_N)
    p.add_argument("--n-extreme", type=int, default=HUMAN_N_EXTREME, help="items per disagreement group")
    p.add_argument("--systems", nargs="+", choices=list(SYSTEMS), default=list(HUMAN_SYSTEMS))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--force", action="store_true", help="overwrite a file that already has labels")
    p.add_argument("--model")
    p = sub.add_parser("carry")
    p.add_argument("--from", dest="from_csv", required=True, help="CSV with item_id, label (and optionally note)")
    p.add_argument("--old", default=str(OUT_ROOT / DEFAULT_MODEL / SUBSET / "human_labels_v1.csv"),
                   help="the earlier sample the item ids refer to")
    p.add_argument("--model")
    p = sub.add_parser("agreement")
    p.add_argument("--model")
    p = sub.add_parser("stability")
    p.add_argument("--other", required=True)
    p.add_argument("--model")
    args = parser.parse_args()
    {"cost": cmd_cost, "run": cmd_run, "export": cmd_export, "carry": cmd_carry, "agreement": cmd_agreement,
     "stability": cmd_stability}[args.cmd](args)


if __name__ == "__main__":
    main()
