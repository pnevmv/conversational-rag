"""Generator input variants: what the generator sees besides the retrieved context.

Retrieval is unchanged; the context of each question is taken from the stored results of the
base pipeline (Step 4 best or E), and only the end of the prompt changes:

    G0  Customer: <current user turn>                              (current setup)
    G1  Customer: <rewritten query>
    G2  last k turns of the gold history, then Customer: <current user turn>
    G3  G2, plus the rewritten query after the user turn

First turns have no history and their rewritten query is the raw turn, so all variants give the
G0 prompt there. k is chosen on dev-500 (--select-k), then the variants are run on the full
validation split (--split validation --k K).

    python experiments/generator_input.py --select-k
    python experiments/generator_input.py --split validation --k 4
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import paired_bootstrap_test
from experiments.run_dev_subset import _build_agent_prompt, _load_few_shot_examples, write_jsonl
from src.data.loader import load_dialogues, load_qa_pairs
from src.evaluation.metrics import compute_metrics, is_abstention
from src.llm import LLMCache, LLMClient, call_meta, generate_batch

RESULTS = PROJECT_ROOT / "experiments" / "results"
CACHE_DIR = PROJECT_ROOT / "experiments" / "cache"
PIPELINES = {"rag_rewrite_rerank_v2": "Step 4 best", "step4_plus_facts": "E"}
K_CHOICES = ("2", "4", "all")
TAIL = "\n\nCustomer: {question}\nAgent:"


def split_dir(split: str) -> Path:
    return RESULTS / ("dev_500" if split == "dev500" else split)


def format_turns(history: List[Dict[str, str]]) -> str:
    return "\n".join(f"{'Customer' if t['role'] == 'user' else 'Agent'}: {t['utterance'].strip()}" for t in history)


def build_prompt(head: str, ex: Dict[str, Any], rewritten: str, variant: str, k: Optional[int]) -> str:
    """head is the G0 prompt without its final Customer/Agent lines."""
    q = ex["question"]
    history = ex["dialogue_history"] if k is None else ex["dialogue_history"][-k:]
    if variant == "G0" or not ex["dialogue_history"]:
        return head + TAIL.format(question=q)
    if variant == "G1":
        return head + TAIL.format(question=rewritten)
    conv = "\n\nConversation so far:\n" + format_turns(history)
    if variant == "G2":
        return head + conv + TAIL.format(question=q)
    if variant == "G3":
        extra = f"\nRewritten question: {rewritten}" if rewritten.strip() != q.strip() else ""
        return head + conv + f"\n\nCustomer: {q}{extra}\nAgent:"
    raise ValueError(variant)


def dialogue_acts(split: str) -> Dict[str, Dict[str, str]]:
    """example_id -> dialogue act of the user turn and of the reference agent turn."""
    out = {}
    for d in load_dialogues("validation" if split == "dev500" else split):
        t = d["turns"]
        for i in range(len(t) - 1):
            if t[i]["role"] == "user" and t[i + 1]["role"] == "agent":
                out[f"{d['dial_id']}_{t[i]['turn_id']}"] = {"user_da": t[i].get("da"), "agent_da": t[i + 1].get("da")}
    return out


def run_variants(split: str, variants: List[str], k_values: List[Optional[int]], workers: int) -> Dict[str, List[Dict]]:
    examples = {ex["example_id"]: ex for ex in load_qa_pairs(split="validation" if split == "dev500" else split,
                                                             max_examples=None)}
    template = _build_agent_prompt(_load_few_shot_examples())
    cache, client = LLMCache(CACHE_DIR), LLMClient()
    out_dir = split_dir(split) / "generator_input"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for base in PIPELINES:
        rows = [json.loads(l) for l in open(split_dir(split) / f"{base}.jsonl", encoding="utf-8")]
        heads = []
        for r in rows:
            head = template.format(context=r["context"], question="\x00").split("\n\nCustomer: \x00")[0]
            assert head + TAIL.format(question=r["question"]) == r["prompt"], r["example_id"]
            heads.append(head)
        for variant in variants:
            for k in (k_values if variant in ("G2", "G3") else [None]):
                name = f"{base}__{variant}" + (f"_k{'all' if k is None else k}" if variant in ("G2", "G3") else "")
                prompts = [build_prompt(h, examples[r["example_id"]], r["rewritten_query"] or r["question"], variant, k)
                           for h, r in zip(heads, rows)]
                print(f"=== {name}: {len(prompts)} prompts", flush=True)
                answers = generate_batch(client, prompts, cache=cache, max_workers=workers, verbose=len(prompts) > 1000,
                                         metas=[call_meta(r, variant, base) for r in rows])
                recs = []
                for r, p, (a, status) in zip(rows, prompts, answers):
                    recs.append({key: r[key] for key in ("example_id", "dialogue_id", "turn_id", "domain", "question",
                                                         "reference_answer", "is_unanswerable", "is_doc_switch",
                                                         "rewritten_query", "recall_at_5")}
                                | {"prompt": p, "model_answer": a, "status": status if a is not None else "error"})
                write_jsonl(recs, out_dir / f"{name}.jsonl")
                results[name] = recs
    return results


def score(recs: List[Dict]) -> Dict[str, float]:
    ok = [r for r in recs if r["model_answer"] is not None]
    return float(np.mean([compute_metrics(r["model_answer"], r["reference_answer"])["f1"] for r in ok]))


def select_k(workers: int) -> None:
    res = run_variants("dev500", ["G2"], [2, 4, None], workers)
    lines = ["# Choice of k for G2 (dev-500)", "", "| k | Step 4 best | E | mean |", "| :--- | :---: | :---: | :---: |"]
    best = None
    for k in K_CHOICES:
        f = [score(res[f"{b}__G2_k{k}"]) for b in PIPELINES]
        lines.append(f"| {k} | {f[0]*100:.1f} | {f[1]*100:.1f} | {np.mean(f)*100:.1f} |")
        if best is None or np.mean(f) > best[1]:
            best = (k, np.mean(f))
    lines += ["", f"Chosen: k = {best[0]}"]
    (split_dir("dev500") / "generator_input" / "select_k.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def evaluate(split: str, k: str) -> None:
    enc = tiktoken.get_encoding("o200k_base")
    das = dialogue_acts(split)
    examples = {ex["example_id"]: ex for ex in load_qa_pairs(split="validation" if split == "dev500" else split,
                                                             max_examples=None)}
    d = split_dir(split) / "generator_input"
    g2 = f"G2_k{k}"
    combo = f"G2_k{k}+abstain(G0)"
    variants = ["G0", "G1", g2, f"G3_k{k}", combo]
    summary: Dict[str, Any] = {"split": split, "k": k, "pipelines": {}}
    lines = [f"# Generator input variants ({split}, k = {k})", ""]
    for base, label in PIPELINES.items():
        data = {v: [json.loads(l) for l in open(d / f"{base}__{v}.jsonl", encoding="utf-8")]
                for v in variants if v != combo}
        # G2 with G0's abstention decision: abstain when G0 abstains, else answer with G2. Needs both calls.
        data[combo] = [a if is_abstention(a["model_answer"] or "") else b for a, b in zip(data["G0"], data[g2])]
        ids = [r["example_id"] for r in data["G0"]]
        valid = [all(data[v][i]["model_answer"] is not None for v in variants) for i in range(len(ids))]
        meta = data["G0"]
        groups = {
            "all": [True] * len(ids),
            "answerable": [not r["is_unanswerable"] for r in meta],
            "unanswerable": [r["is_unanswerable"] for r in meta],
            "first turn": [not examples[i]["dialogue_history"] for i in ids],
        }
        groups["follow-up"] = [not x for x in groups["first turn"]]
        for da in ("respond_solution", "query_condition", "respond_no_solution", "respond_solution_positive",
                   "respond_solution_negative"):
            groups[f"agent: {da}"] = [das[i]["agent_da"] == da for i in ids]
        for da in ("query_condition", "query_solution", "response_positive", "response_negative"):
            groups[f"user: {da}"] = [das[i]["user_da"] == da for i in ids]

        f1 = {v: np.array([compute_metrics(r["model_answer"] or "", r["reference_answer"])["f1"] for r in data[v]]) for v in variants}
        abst = {v: np.array([is_abstention(r["model_answer"] or "") for r in data[v]]) for v in variants}
        tok = {v: float(np.mean([len(enc.encode(r["prompt"], disallowed_special=())) for r in data[v]]))
               for v in variants if v != combo}
        # G0 always runs; G2 only when G0 did not abstain.
        tok[combo] = tok["G0"] + float(np.mean([0 if is_abstention(r0["model_answer"] or "") else
                                                len(enc.encode(r2["prompt"], disallowed_special=()))
                                                for r0, r2 in zip(data["G0"], data[g2])]))
        unans = np.array(groups["unanswerable"])
        s = {"n_errors": int(len(ids) - sum(valid)), "variants": {}}
        for v in variants:
            vs = {"input_tokens_per_turn": tok[v],
                  "abstain_rate": float(abst[v].mean()),
                  "abstain_recall": float(abst[v][unans].mean()),
                  "false_abstention": float(abst[v][~unans].mean()),
                  "groups": {}}
            for g, mask in groups.items():
                m = np.array(mask) & np.array(valid)
                if not m.any():
                    continue
                entry = {"n": int(m.sum()), "f1": float(f1[v][m].mean())}
                if v != "G0":
                    entry["delta_vs_G0"] = paired_bootstrap_test(list(f1[v][m]), list(f1["G0"][m]))
                vs["groups"][g] = entry
            s["variants"][v] = vs
        summary["pipelines"][base] = s

        lines += [f"## {label}", "", f"Questions with an API error in any variant (left out): {s['n_errors']}", "",
                  "| Group | n | " + " | ".join(variants) + " |", "| :--- | ---: |" + " :---: |" * len(variants)]
        for g in groups:
            if g not in s["variants"]["G0"]["groups"]:
                continue
            cells = []
            for v in variants:
                e = s["variants"][v]["groups"][g]
                c = f"{e['f1']*100:.1f}"
                if "delta_vs_G0" in e:
                    t = e["delta_vs_G0"]
                    c += f" ({t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}])"
                cells.append(c)
            lines.append(f"| {g} | {s['variants']['G0']['groups'][g]['n']} | " + " | ".join(cells) + " |")
        lines += ["", "| | " + " | ".join(variants) + " |", "| :--- |" + " :---: |" * len(variants)]
        lines.append("| abstain recall / false abstention | " + " | ".join(
            f"{s['variants'][v]['abstain_recall']*100:.1f} / {s['variants'][v]['false_abstention']*100:.1f}" for v in variants) + " |")
        lines.append("| generation input tokens / turn | " + " | ".join(
            f"{s['variants'][v]['input_tokens_per_turn']:.0f}" for v in variants) + " |")
        lines.append("")
        if base == "rag_rewrite_rerank_v2":
            write_examples(d, data["G0"], data[g2], examples, das)
    lines.append(f"{combo}: the G0 answer when G0 abstains, else the G2 answer (G0 always runs and G2 only when G0 "
                 "does not abstain, so its input tokens include both calls). It abstains when either G0 or the G2 "
                 "answer abstains.")
    (d / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (d / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def write_examples(d: Path, g0: List[Dict], g2: List[Dict], examples: Dict[str, Dict], das: Dict, n: int = 10) -> None:
    """Unanswerable turns where G0 abstained and G2 answered (Step 4 pipeline), n drawn with seed 42."""
    import random
    cand = [(a, b) for a, b in zip(g0, g2) if a["is_unanswerable"] and is_abstention(a["model_answer"] or "")
            and not is_abstention(b["model_answer"] or "")]
    picked = sorted(random.Random(42).sample(cand, min(n, len(cand))), key=lambda ab: ab[0]["example_id"])
    lines = ["# Unanswerable turns: G0 abstains, G2 answers (Step 4 best, validation)", "",
             f"{len(cand)} unanswerable turns have this pattern; {len(picked)} drawn at random (seed 42). "
             "The reference of every one is \"Unfortunately, no relevant information is found.\"", ""]
    for i, (a, b) in enumerate(picked, 1):
        ex = examples[a["example_id"]]
        lines += [f"## {i}. {a['example_id']} ({a['domain']}, user act: {das[a['example_id']]['user_da']})", "",
                  "Last turns of the history:", ""]
        lines += [f"> {'Customer' if t['role'] == 'user' else 'Agent'}: {t['utterance'].strip()}  "
                  for t in ex["dialogue_history"][-4:]]
        lines += ["", f"**Customer:** {a['question']}", "", f"**Rewritten query:** {a['rewritten_query']}", "",
                  f"**G2 answer:** {b['model_answer']}", ""]
    (d / "unanswerable_examples.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--select-k", action="store_true")
    parser.add_argument("--split", choices=["dev500", "validation"], default="validation")
    parser.add_argument("--k", choices=K_CHOICES)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--evaluate-only", action="store_true")
    args = parser.parse_args()
    if args.select_k:
        select_k(args.workers)
        return
    if not args.k:
        parser.error("--k is required (run --select-k first)")
    if not args.evaluate_only:
        run_variants(args.split, ["G0", "G1", "G2", "G3"], [None if args.k == "all" else int(args.k)], args.workers)
    evaluate(args.split, args.k)


if __name__ == "__main__":
    main()
