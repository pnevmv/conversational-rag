"""Source sections for each answer (validation only), for the final system: passages + 30 graph facts
(E), gpt-5.4-nano, G2 + abstain(G0).

    A  post-hoc attribution, no LLM calls: the source of an answer is the candidate section (one of
       the 5 passages, or the evidence section of one of the facts in the prompt) whose text in the
       prompt shares the most answer tokens (F1 normalisation). Refusals get no source.
    B  citations by the generator: the G2 prompt asks the model to end its answer with the numbers of
       the passages ([2]) and facts ([F7]) it used; citations are stripped before F1. Dev-500 first;
       full validation only if F1 drops by at most 0.3 points.
    C  five demo turns, drawn with a fixed seed.

    python experiments/sources.py posthoc
    python experiments/sources.py cite --split dev500      # then --split validation if allowed
    python experiments/sources.py examples
"""
import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import experiments.graph_rag as gr
from experiments.evaluate_diagnostics import paired_bootstrap_test
from experiments.generator_input import TAIL, build_prompt
from src.evaluation.metrics import _normalize, compute_metrics, is_abstention
from src.kg_rag.queries import load_step4
from src.llm import LLMCache, LLMClient, call_meta, generate_batch

VAL = PROJECT_ROOT / "experiments" / "results" / "validation"
GEN = VAL / "generator_input"
OUT = VAL / "sources"
DEV_IDS = PROJECT_ROOT / "data" / "dev_500_ids.json"
CACHE_DIR = PROJECT_ROOT / "experiments" / "cache"
ABSTAIN = "Unfortunately, no relevant information is found."
MAX_F1_DROP = 0.003
CITE_INSTRUCTION = ("After your answer, add in square brackets the numbers of the passages and facts you used, "
                    "for example [2] or [2, F7]; passages are numbered [1] to [5], facts [F1] to [F30].")


def load(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def tokens(text: str) -> List[str]:
    return _normalize(text or "").split()


# ---------------------------------------------------------------------------- shared data
def e_system() -> Dict[str, Dict[str, Any]]:
    """Final answers of E (G2 + abstain(G0)) from the cached generator-input runs, with the context."""
    g0 = load(GEN / "step4_plus_facts__G0.jsonl")
    g2 = {r["example_id"]: r for r in load(GEN / "step4_plus_facts__G2_kall.jsonl")}
    rec = {r["example_id"]: r for r in load(VAL / "step4_plus_facts.jsonl")}
    out = {}
    for r in g0:
        i = r["example_id"]
        ans = ABSTAIN if is_abstention(r["model_answer"] or "") else g2[i]["model_answer"]
        out[i] = {**r, "model_answer": ans, "g0_answer": r["model_answer"], "context": rec[i]["context"],
                  "retrieved_sections": rec[i]["retrieved_sections"]}
    return out


def candidates(row: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(label, section id, text shown in the prompt): passages [1]-[5], then facts [F1]-[F30]."""
    ctx, _, facts = row["context"].partition("\n\nFacts:\n")
    blocks = re.split(r"\n\n(?=\[\d+\] )", ctx)
    out = []
    for k, (sid, block) in enumerate(zip(row["retrieved_sections"], blocks), start=1):
        out.append((str(k), sid, block))
    fact_blocks = re.split(r"\n(?=\[\d+\] )", facts) if facts else []
    for fb in fact_blocks:
        m = re.match(r"\[(\d+)\] ", fb)
        sids = gr.fact_sections_of("\n\nFacts:\n" + fb)
        if m and sids:
            out.append((f"F{m.group(1)}", next(iter(sids)), fb))
    return out


def gold_sections() -> Dict[str, set]:
    return {i: set(r["gold_sections"]) for i, r in load_step4("validation")["records"].items()}


def hits() -> Dict[str, bool]:
    return {r["example_id"]: r["recall_at_5"] > 0 for r in load(VAL / "rag_rewrite_rerank_v2.jsonl")}


# ---------------------------------------------------------------------------- A: post-hoc
def rank_sources(answer: str, cands: List[Tuple[str, str, str]]) -> List[str]:
    """Candidate sections ordered by the share of the answer's (unique) tokens their prompt text covers;
    a section that appears several times keeps its best score; ties keep the prompt order."""
    a = set(tokens(answer))
    best: Dict[str, Tuple[float, int]] = {}
    for pos, (_, sid, text) in enumerate(cands):
        sc = len(a & set(tokens(text))) / max(1, len(a))
        if sid not in best or sc > best[sid][0]:
            best[sid] = (sc, -pos if sid not in best else best[sid][1])
    return [sid for sid, _ in sorted(best.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))]


def posthoc() -> Dict[str, Any]:
    E, gold, hit = e_system(), gold_sections(), hits()
    rows = []
    for i, r in E.items():
        if r["model_answer"] is None or is_abstention(r["model_answer"]):
            continue
        cands = candidates(r)
        ranked = rank_sources(r["model_answer"], cands)
        rows.append({"id": i, "hit": hit[i], "top1": ranked[0] in gold[i] if ranked else False,
                     "top2": bool(set(ranked[:2]) & gold[i]),
                     "any": bool({sid for _, sid, _ in cands} & gold[i]), "unans": r["is_unanswerable"]})
    res = {"answered": len(rows), "total": len(E)}
    for name, keep in (("all answered", lambda x: True), ("passages hit", lambda x: x["hit"]),
                       ("passages miss", lambda x: not x["hit"]), ("answerable", lambda x: not x["unans"])):
        sub = [x for x in rows if keep(x)]
        res[name] = {"n": len(sub), "top1": float(np.mean([x["top1"] for x in sub])),
                     "top2": float(np.mean([x["top2"] for x in sub])), "any": float(np.mean([x["any"] for x in sub]))}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "posthoc.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


# ---------------------------------------------------------------------------- B: citations
CITE_RE = re.compile(r"\s*\[(?:\s*F?\d+\s*(?:,\s*F?\d+\s*)*)\]")


def strip_citations(answer: str) -> str:
    return CITE_RE.sub("", answer or "").strip()


def parse_citations(answer: str) -> List[str]:
    labels = []
    for group in re.findall(r"\[((?:\s*F?\d+\s*,?)+)\]", answer or ""):
        labels += [x.strip() for x in group.split(",") if x.strip()]
    return labels


def cite_template() -> str:
    t = gr.template()
    anchor = "If the context does not contain the answer"
    assert anchor in t
    return t.replace(anchor, CITE_INSTRUCTION + "\n" + anchor, 1)


def cite_context(context: str) -> str:
    ctx, sep, facts = context.partition("\n\nFacts:\n")
    return ctx + sep + re.sub(r"^\[(\d+)\] ", r"[F\1] ", facts, flags=re.M) if sep else context


def run_cite(split: str) -> None:
    E = e_system()
    exs = gr.examples()
    ids = json.loads(DEV_IDS.read_text()) if split == "dev500" else list(E)
    tmpl = cite_template()
    rw = gr.rewrites()
    need = [i for i in ids if E[i]["g0_answer"] is not None and not is_abstention(E[i]["g0_answer"])]
    prompts = {}
    for i in need:
        head = tmpl.format(context=cite_context(E[i]["context"]), question="\x00").split("\n\nCustomer: \x00")[0]
        prompts[i] = build_prompt(head, exs[i], rw[i], "G2", None)
        if not exs[i]["dialogue_history"]:  # first turns: G2 is the G0 prompt, here with the citation request
            prompts[i] = head + TAIL.format(question=exs[i]["question"])
    print(f"=== citations ({split}): G2 on {len(need)} questions", flush=True)
    ans = generate_batch(LLMClient(), [prompts[i] for i in need], cache=LLMCache(CACHE_DIR), max_workers=12,
                         verbose=len(need) > 1000, metas=[call_meta(exs[i], "G2-cite", "sources") for i in need])
    rows = []
    for i in ids:
        raw = None
        if i in prompts:
            raw = ans[need.index(i)][0]
        final = ABSTAIN if i not in prompts else raw
        rows.append({"example_id": i, "prompt": prompts.get(i), "raw_answer": raw, "model_answer": final,
                     "reference_answer": exs[i]["reference_answer"], "is_unanswerable": exs[i]["is_unanswerable"]})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"cite_{split}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  {sum(1 for r in rows if r['example_id'] in prompts and r['raw_answer'] is None)} errors", flush=True)


def eval_cite(split: str) -> Dict[str, Any]:
    E, gold, hit = e_system(), gold_sections(), hits()
    enc = tiktoken.get_encoding("o200k_base")
    ntok = lambda s: len(enc.encode(s or "", disallowed_special=()))
    rows = load(OUT / f"cite_{split}.jsonl")
    ids = [r["example_id"] for r in rows if r["model_answer"] is not None]
    cite = {r["example_id"]: r for r in rows}
    f1 = lambda a, ref: compute_metrics(a or "", ref)["f1"]
    fc = [f1(strip_citations(cite[i]["model_answer"]), cite[i]["reference_answer"]) for i in ids]
    fe = [f1(E[i]["model_answer"], E[i]["reference_answer"]) for i in ids]
    ans = [k for k, i in enumerate(ids) if not cite[i]["is_unanswerable"]]
    t_all = paired_bootstrap_test(fc, fe)
    t_ans = paired_bootstrap_test([fc[k] for k in ans], [fe[k] for k in ans])
    fa = lambda d: float(np.mean([is_abstention(strip_citations(d[i]["model_answer"])) for i in ids if not cite[i]["is_unanswerable"]]))
    # citation precision on answered questions
    answered = [i for i in ids if not is_abstention(strip_citations(cite[i]["model_answer"]))]
    prec = []
    no_cite = invalid = 0
    for i in answered:
        labels = parse_citations(cite[i]["model_answer"])
        cmap = {lab: sid for lab, sid, _ in candidates(E[i])}
        if not labels:
            no_cite += 1
            continue
        sids = [cmap[l] for l in labels if l in cmap]
        if len(sids) < len(labels):
            invalid += 1
        if not sids:
            continue
        prec.append({"id": i, "first": sids[0] in gold[i], "any": bool(set(sids) & gold[i]), "n": len(set(sids)),
                     "hit": hit[i]})
    g2_in_e = {r["example_id"]: r["prompt"] for r in load(GEN / "step4_plus_facts__G2_kall.jsonl")}
    g2_out_e = {r["example_id"]: r["model_answer"] for r in load(GEN / "step4_plus_facts__G2_kall.jsonl")}
    called = [i for i in ids if cite[i]["prompt"]]
    res = {"split": split, "n": len(ids),
           "f1_cite": float(np.mean(fc)), "f1_E": float(np.mean(fe)), "delta_all": t_all, "delta_answerable": t_ans,
           "false_abstention_cite": fa(cite), "false_abstention_E": fa(E),
           "answered": len(answered), "no_citation": no_cite, "invalid_citation": invalid,
           "precision_first": float(np.mean([p["first"] for p in prec])) if prec else None,
           "precision_any": float(np.mean([p["any"] for p in prec])) if prec else None,
           "precision_first_hit": float(np.mean([p["first"] for p in prec if p["hit"]])) if prec else None,
           "precision_first_miss": float(np.mean([p["first"] for p in prec if not p["hit"]])) if prec else None,
           "sources_per_answer": float(np.mean([p["n"] for p in prec])) if prec else None,
           "extra_input_tokens_per_g2_call": float(np.mean([ntok(cite[i]["prompt"]) - ntok(g2_in_e[i]) for i in called])),
           "extra_output_tokens_per_g2_call": float(np.mean([ntok(cite[i]["raw_answer"]) - ntok(g2_out_e[i]) for i in called if cite[i]["raw_answer"] is not None]))}
    (OUT / f"cite_{split}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


# ---------------------------------------------------------------------------- C: demo examples
def examples(split: str, n: int = 5) -> None:
    E, gold = e_system(), gold_sections()
    exs = gr.examples()
    rows = {r["example_id"]: r for r in load(OUT / f"cite_{split}.jsonl")}
    answered = sorted(i for i, r in rows.items() if r["model_answer"] and not is_abstention(strip_citations(r["model_answer"])))
    picked = sorted(random.Random(42).sample(answered, n))
    g = gr.kg()
    lines = ["# Demo: answers with their sources", "",
             f"Five answered turns of the {'dev-500 subset' if split == 'dev500' else 'validation split'}, drawn at random "
             "(seed 42) among the answered ones; final system with the citation prompt. Sources are the passages and "
             "facts cited by the model, shown as document title and section heading; gold = the section holds the "
             "grounding span of the reference answer.", ""]
    for k, i in enumerate(picked, 1):
        ex, r = exs[i], rows[i]
        cmap = {lab: sid for lab, sid, _ in candidates(E[i])}
        labels = parse_citations(r["model_answer"])
        lines += [f"## {k}. {ex['domain'].upper()}, turn {ex['turn_id']}", ""]
        if ex["dialogue_history"]:
            t = ex["dialogue_history"][-1]
            lines.append(f"> {'User' if t['role'] == 'user' else 'Agent'} (previous turn): {t['utterance'].strip()}  ")
        lines += [f"> **User:** {ex['question']}", "", f"**Answer:** {strip_citations(r['model_answer'])}", "",
                  f"**Reference:** {ex['reference_answer']}", "", "**Sources:**", ""]
        seen = set()
        for lab in labels:
            sid = cmap.get(lab)
            if sid is None:
                lines.append(f"* [{lab}] (not a valid passage or fact number)")
                continue
            if sid in seen:
                continue
            seen.add(sid)
            sec = g.sections[sid]
            title = re.sub(r"#\d+$", "", sec["title"])
            name = title + (f" — {sec['section_title']}" if sec.get("section_title") else "")
            lines.append(f"* [{lab}] {name}: {'gold' if sid in gold[i] else 'not gold'}")
        if not labels:
            lines.append("* (no citation)")
        lines.append("")
    (OUT / "demo_examples.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["posthoc", "cite", "eval", "examples"])
    parser.add_argument("--split", choices=["dev500", "validation"], default="dev500")
    args = parser.parse_args()
    if args.cmd == "posthoc":
        print(json.dumps(posthoc(), indent=2))
    elif args.cmd == "cite":
        run_cite(args.split)
        print(json.dumps(eval_cite(args.split), indent=2))
    elif args.cmd == "eval":
        print(json.dumps(eval_cite(args.split), indent=2))
    else:
        examples(args.split)


if __name__ == "__main__":
    main()
