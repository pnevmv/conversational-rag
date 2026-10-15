"""Cheaper abstention decisions for the conversational generator (G2, whole gold history).

G2+abstain(G0) runs the G0 generator only to decide whether to abstain. Two cheaper decisions
replace it here; the answer is still the G2 answer whenever the decision is to answer:

    (a) classifier: one gpt-5.4-nano call (reasoning effort none, at most 16 output tokens) on
        the retrieved context, the history and the current turn, answering yes or no;
    (b) threshold: abstain when the top-1 reranker score of the Step 4 ranking is below t,
        with t chosen on dev-500 (best F1 of G2 + threshold, per pipeline).

Token usage of the classifier calls is recorded from the API. Generator tokens are counted
from the stored prompts and answers (o200k_base), without hidden reasoning tokens.

    python experiments/abstention_decision.py [--workers 12]
"""
import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import paired_bootstrap_test
from experiments.generator_input import format_turns
from src.data.loader import load_qa_pairs
from src.evaluation.metrics import compute_metrics, is_abstention
from src.kg_rag.queries import load_step4
from src.llm import LLMClient

RESULTS = PROJECT_ROOT / "experiments" / "results"
CACHE_DIR = PROJECT_ROOT / "experiments" / "cache" / "classifier"
PIPELINES = {"rag_rewrite_rerank_v2": "Step 4 best", "step4_plus_facts": "E"}
ABSTAIN = "Unfortunately, no relevant information is found."
CALL_PARAMS: Dict[str, Any] = {"reasoning": {"effort": "none"}, "temperature": 0, "max_output_tokens": 16}

CLASSIFIER_PROMPT = (
    "You check whether a government services agent can answer the customer's last message using "
    "only the context below. Reply with one word: yes if the context contains the information "
    "needed to answer it, no if it does not.\n\n"
    "Context:\n{context}\n\n{conversation}Customer: {question}\nAnswerable:"
)


def classifier_prompt(context: str, ex: Dict[str, Any]) -> str:
    conv = f"Conversation so far:\n{format_turns(ex['dialogue_history'])}\n\n" if ex["dialogue_history"] else ""
    return CLASSIFIER_PROMPT.format(context=context, conversation=conv, question=ex["question"])


def classify(client: LLMClient, prompt: str, retries: int = 5) -> Dict[str, Any]:
    key = hashlib.sha256((json.dumps(CALL_PARAMS, sort_keys=True) + prompt).encode("utf-8")).hexdigest()
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(retries):
        try:
            r = client.client.responses.create(model=client.default_model, input=prompt, **CALL_PARAMS)
            u = r.usage
            out = {"text": r.output_text, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                   "reasoning_tokens": getattr(u.output_tokens_details, "reasoning_tokens", 0) or 0}
            path.write_text(json.dumps(out), encoding="utf-8")
            return out
        except Exception as e:  # noqa: BLE001
            if "content_filter" in str(e) or attempt == retries - 1:
                return {"text": None, "error": str(e)[:200], "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
            time.sleep(2 ** attempt)


def says_no(c: Dict[str, Any]) -> bool:
    return bool(c["text"]) and c["text"].strip().lower().startswith("no")


def load(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def f1(answer: str, ref: str) -> float:
    return compute_metrics(answer or "", ref)["f1"]


def choose_threshold(base: str) -> float:
    """Threshold on the top-1 reranker score with the best F1 of G2 + threshold on dev-500."""
    rows = load(RESULTS / "dev_500" / "generator_input" / f"{base}__G2_kall.jsonl")
    recs = load_step4("dev500")["records"]
    score = np.array([recs[r["example_id"]]["step4_ranking"][0]["reranker_score"] for r in rows])
    f_ans = np.array([f1(r["model_answer"], r["reference_answer"]) for r in rows])
    f_abs = np.array([f1(ABSTAIN, r["reference_answer"]) for r in rows])
    best = (-np.inf, 0.0)
    for t in np.concatenate([[0.0], np.unique(score)]):
        m = float(np.where(score < t, f_abs, f_ans).mean())
        if m > best[0]:
            best = (m, float(t))
    return best[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    enc = tiktoken.get_encoding("o200k_base")
    ntok = lambda s: len(enc.encode(s or "", disallowed_special=()))
    examples = {ex["example_id"]: ex for ex in load_qa_pairs(split="validation", max_examples=None)}
    recs = load_step4("validation")["records"]
    client = LLMClient()
    d = RESULTS / "validation" / "generator_input"
    summary: Dict[str, Any] = {"call_params": CALL_PARAMS, "pipelines": {}}
    lines = ["# Abstention decisions for the conversational generator (validation)", "",
             "Generator G2 (whole gold history) in every row; only the decision to abstain changes. "
             "Δ is the paired bootstrap difference to G2 + abstain(G0). Tokens per turn: the decision "
             "call (if any) plus the G2 call when the decision is to answer; generator tokens are counted "
             "from the text (no reasoning tokens), classifier tokens come from the API.", ""]

    for base, label in PIPELINES.items():
        ctx = {r["example_id"]: r["context"] for r in load(RESULTS / "validation" / f"{base}.jsonl")}
        g0 = load(d / f"{base}__G0.jsonl")
        g2 = load(d / f"{base}__G2_kall.jsonl")
        ids = [r["example_id"] for r in g0]
        prompts = [classifier_prompt(ctx[i], examples[i]) for i in ids]
        print(f"=== {label}: {len(prompts)} classifier calls", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            cls = list(pool.map(lambda p: classify(client, p), prompts))
        errors = sum(c["text"] is None for c in cls)
        unparsed = sum(1 for c in cls if c["text"] and (c["text"].strip().lower().split() or [""])[0].strip(".,!")
                       not in ("yes", "no"))
        t = choose_threshold(base)
        score = np.array([recs[i]["step4_ranking"][0]["reranker_score"] for i in ids])

        refs = [r["reference_answer"] for r in g0]
        unans = np.array([r["is_unanswerable"] for r in g0])
        g0_abst = np.array([is_abstention(r["model_answer"] or "") for r in g0])
        cls_no = np.array([says_no(c) for c in cls])
        thr_no = score < t
        g2_in = np.array([ntok(r["prompt"]) for r in g2]); g2_out = np.array([ntok(r["model_answer"]) for r in g2])
        g0_in = np.array([ntok(r["prompt"]) for r in g0]); g0_out = np.array([ntok(r["model_answer"]) for r in g0])
        c_in = np.array([c["input_tokens"] for c in cls]); c_out = np.array([c["output_tokens"] for c in cls])

        systems = {
            "G2 (no decision step)": (np.zeros(len(ids), bool), g2_in, g2_out),
            "G2 + abstain(G0)": (g0_abst, g0_in + np.where(g0_abst, 0, g2_in), g0_out + np.where(g0_abst, 0, g2_out)),
            "G2 + classifier": (cls_no, c_in + np.where(cls_no, 0, g2_in), c_out + np.where(cls_no, 0, g2_out)),
            f"G2 + reranker threshold (t = {t:.4f})": (thr_no, np.where(thr_no, 0, g2_in), np.where(thr_no, 0, g2_out)),
        }
        ref_f1 = None
        s: Dict[str, Any] = {"classifier_errors": errors, "classifier_unparsed": unparsed, "threshold": t,
                             "classifier_says_no": float(cls_no.mean()), "threshold_abstains": float(thr_no.mean()),
                             "classifier_reasoning_tokens": int(sum(c["reasoning_tokens"] for c in cls)), "systems": {}}
        lines += [f"## {label}", "",
                  f"Classifier: {errors} API errors (counted as yes), {unparsed} answers not yes/no; says no on "
                  f"{cls_no.mean()*100:.1f}% of the turns. Threshold chosen on dev-500: {t:.4f} "
                  f"(abstains on {thr_no.mean()*100:.1f}% of the validation turns).", "",
                  "| Decision | F1 all | F1 answerable | F1 unanswerable | Δ all vs G2+abstain(G0) | abstain recall / false abstention | in / out tokens per turn |",
                  "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |"]
        for name, (decide_no, tin, tout) in systems.items():
            answers = [ABSTAIN if no else r["model_answer"] for no, r in zip(decide_no, g2)]
            f = np.array([f1(a, ref) for a, ref in zip(answers, refs)])
            ab = np.array([is_abstention(a or "") for a in answers])
            if name == "G2 + abstain(G0)":
                ref_f1 = f
            e = {"f1": float(f.mean()), "f1_answerable": float(f[~unans].mean()), "f1_unanswerable": float(f[unans].mean()),
                 "abstain_recall": float(ab[unans].mean()), "false_abstention": float(ab[~unans].mean()),
                 "input_tokens_per_turn": float(tin.mean()), "output_tokens_per_turn": float(tout.mean())}
            s["systems"][name] = e
            s["systems"][name]["_f1"] = f
        for name, e in s["systems"].items():
            f = e.pop("_f1")
            delta = "-"
            if name != "G2 + abstain(G0)":
                tt = paired_bootstrap_test(list(f), list(ref_f1))
                e["delta_vs_G2_abstain_G0"] = tt
                delta = f"{tt['mean_diff']*100:+.1f} [{tt['ci_low']*100:.1f}, {tt['ci_high']*100:.1f}]"
            lines.append(f"| {name} | {e['f1']*100:.1f} | {e['f1_answerable']*100:.1f} | {e['f1_unanswerable']*100:.1f} | "
                         f"{delta} | {e['abstain_recall']*100:.1f} / {e['false_abstention']*100:.1f} | "
                         f"{e['input_tokens_per_turn']:.0f} / {e['output_tokens_per_turn']:.0f} |")
        lines.append("")
        summary["pipelines"][base] = s

    (d / "abstention_decision.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (d / "abstention_decision.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
