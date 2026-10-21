"""Generator model comparison on the validation split: gpt-5.4-nano, gpt-5-nano and gpt-6-luna.

The system is the conversational generator with the abstention decision of the G0 prompt
(G2 + abstain(G0)), for the best passage pipeline and for passages + graph facts (E). Only the
generator calls change model: the G0 and G2 prompts are read unchanged from
experiments/results/validation/generator_input/, so the rewrites, retrieval, graph facts and
contexts are identical. G0 runs on every question; G2 runs only when G0 does not abstain, and on
first turns (no history) the G2 prompt equals the G0 prompt and the G0 answer is reused.

Every API call logs its usage, both here and in the shared log of src/llm/client.py
(experiments/logs/llm_usage.jsonl), (input, cached input, output, reasoning tokens) with the model,
pipeline, call type, conversation and turn. Endpoints, keys and deployments come from .env:

    gpt-5.4-nano  AZURE_OPENAI_BASE_URL, AZURE_OPENAI_API_KEY, LLM_MODEL
    gpt-5-nano    AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_KEY, AZURE_FOUNDRY_DEPLOYMENT
    gpt-6-luna    AZURE_LUNA_ENDPOINT, AZURE_LUNA_KEY, AZURE_LUNA_DEPLOYMENT

All three models are run fresh on the full split; the cached gpt-5.4-nano answers of the generator-input
experiment (the system as reported, no usage recorded) are kept as an extra row.

    python experiments/model_comparison.py run --model gpt-6-luna --pilot
    python experiments/model_comparison.py run --model gpt-6-luna
    python experiments/model_comparison.py report
"""
import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import paired_bootstrap_test
from src.evaluation.metrics import compute_metrics, is_abstention
from src.llm.client import DEFAULT_BASE_URL, DEFAULT_MODEL, call_meta, log_usage

load_dotenv(PROJECT_ROOT / ".env")

GEN_DIR = PROJECT_ROOT / "experiments" / "results" / "validation" / "generator_input"
OUT_DIR = PROJECT_ROOT / "experiments" / "results" / "validation" / "model_comparison"
CACHE_ROOT = PROJECT_ROOT / "experiments" / "cache" / "models"
PIPELINES = {"rag_rewrite_rerank_v2": "Passages", "step4_plus_facts": "Passages + graph facts"}
ABSTAIN = "Unfortunately, no relevant information is found."
PILOT_MIN_TURNS = 500
BASELINE = "gpt-5.4-nano"

MODELS = {
    "gpt-5.4-nano": ("AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY", "LLM_MODEL"),
    "gpt-5-nano": ("AZURE_FOUNDRY_ENDPOINT", "AZURE_FOUNDRY_KEY", "AZURE_FOUNDRY_DEPLOYMENT"),
    "gpt-6-luna": ("AZURE_LUNA_ENDPOINT", "AZURE_LUNA_KEY", "AZURE_LUNA_DEPLOYMENT"),
}
# USD per 1M tokens, Global Standard deployment, from the Azure Retail Prices API
# (prices.azure.com, region eastus2, checked 2026-10-21). gpt-6-luna: short-context meters.
PRICES = {
    "gpt-5.4-nano": {"input": 0.20, "cached_input": 0.02, "output": 1.25,
                     "meters": "5.4 nano Inp / cd Inp / Opt Gl"},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40,
                   "meters": "GPT 5 Nano Inpt / cchd Inpt / outpt Glbl"},
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50,
                   "meters": "6-luna ShortCo Inp / Cd Inp / Opt Std Gl"},
}


class ModelClient:
    def __init__(self, model: str):
        url_var, key_var, dep_var = MODELS[model]
        # gpt-5.4-nano falls back to the defaults of src/llm/client.py, like the main client.
        base_url = os.getenv(url_var) or (DEFAULT_BASE_URL if model == BASELINE else None)
        missing = [v for v, val in ((url_var, base_url), (key_var, os.getenv(key_var))) if not val]
        if missing:
            raise SystemExit(f"missing in .env: {', '.join(missing)}")
        self.model = model
        self.deployment = os.getenv(dep_var) or (DEFAULT_MODEL if model == BASELINE else None)
        self.client = OpenAI(base_url=base_url, api_key=os.getenv(key_var), timeout=180.0)
        self.cache_dir = CACHE_ROOT / model
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def call(self, prompt: str, meta: Optional[Dict[str, Any]] = None, retries: int = 6) -> Dict[str, Any]:
        path = self.cache_dir / f"{hashlib.sha256(prompt.encode('utf-8')).hexdigest()}.json"
        if path.exists():
            out = json.loads(path.read_text(encoding="utf-8"))
            log_usage(self.deployment, _usage(out), meta, cache_hit=True)
            return {**out, "cache_hit": True}
        for attempt in range(retries):
            try:
                r = self.client.responses.create(model=self.deployment, input=prompt)
                u = r.usage
                out = {"text": r.output_text, "status": "ok",
                       "input_tokens": u.input_tokens,
                       "cached_tokens": getattr(u.input_tokens_details, "cached_tokens", 0) or 0,
                       "output_tokens": u.output_tokens,
                       "reasoning_tokens": getattr(u.output_tokens_details, "reasoning_tokens", 0) or 0}
                path.write_text(json.dumps(out), encoding="utf-8")
                log_usage(self.deployment, _usage(out), meta)
                return {**out, "cache_hit": False}
            except Exception as e:  # noqa: BLE001 - the key is never part of the message
                msg = type(e).__name__ + ": " + str(e)[:200]
                if "content_filter" in msg or "ResponsibleAIPolicyViolation" in msg:
                    out = {"text": None, "status": "content_filter", "input_tokens": 0, "cached_tokens": 0,
                           "output_tokens": 0, "reasoning_tokens": 0}
                    path.write_text(json.dumps(out), encoding="utf-8")
                    return {**out, "cache_hit": False}
                if attempt == retries - 1:
                    return {"text": None, "status": "error: " + msg, "input_tokens": 0, "cached_tokens": 0,
                            "output_tokens": 0, "reasoning_tokens": 0, "cache_hit": False}
                time.sleep(min(60, 2 ** attempt * 2))


def _usage(out: Dict[str, Any]) -> Dict[str, Any]:
    return {k: out[k] for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens")}


def load(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def pilot_ids(rows: List[Dict[str, Any]]) -> set:
    """Whole conversations drawn at random (seed 42) until they hold at least 500 questions."""
    by_dial: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        by_dial[r["dialogue_id"]].append(r["example_id"])
    dials = sorted(by_dial)
    random.Random(42).shuffle(dials)
    ids: set = set()
    for d in dials:
        ids.update(by_dial[d])
        if len(ids) >= PILOT_MIN_TURNS:
            break
    return ids


def run(model: str, pilot: bool, workers: int) -> None:
    client = ModelClient(model)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    tag = "pilot" if pilot else "full"
    for base in PIPELINES:
        g0 = load(GEN_DIR / f"{base}__G0.jsonl")
        g2 = {r["example_id"]: r for r in load(GEN_DIR / f"{base}__G2_kall.jsonl")}
        keep = pilot_ids(g0) if pilot else None
        rows = [r for r in g0 if keep is None or r["example_id"] in keep]
        usage_path = OUT_DIR / f"{model}__{base}__usage_{tag}.jsonl"
        usage_path.unlink(missing_ok=True)
        print(f"=== {model} / {base}: {len(rows)} questions ({tag})", flush=True)

        def log(r, call_type, res):
            row = {"model": model, "pipeline": base, "call_type": call_type, "example_id": r["example_id"],
                   "dialogue_id": r["dialogue_id"], "turn_id": r["turn_id"],
                   **{k: res[k] for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens",
                                          "status", "cache_hit")}}
            with lock, open(usage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

        def one(r):
            a0 = client.call(r["prompt"], call_meta(r, "G0", base))
            log(r, "G0", a0)
            p2 = g2[r["example_id"]]["prompt"]
            if a0["text"] is None:
                final, status = None, a0["status"]
            elif is_abstention(a0["text"]):
                final, status = ABSTAIN, "ok"
            elif p2 == r["prompt"]:
                final, status = a0["text"], "ok"
            else:
                a2 = client.call(p2, call_meta(r, "G2", base))
                log(r, "G2", a2)
                final, status = a2["text"], a2["status"]
            return {k: r[k] for k in ("example_id", "dialogue_id", "turn_id", "domain", "question",
                                      "reference_answer", "is_unanswerable")} | {
                "g0_answer": a0["text"], "model_answer": final, "status": status}

        done, t0, out = 0, time.time(), []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for rec in pool.map(one, rows):
                out.append(rec)
                done += 1
                if done % 250 == 0:
                    print(f"  {done}/{len(rows)}  {time.time() - t0:.0f}s", flush=True)
        with open(OUT_DIR / f"{model}__{base}__answers_{tag}.jsonl", "w", encoding="utf-8") as f:
            for rec in out:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        errs = sum(1 for r in out if r["model_answer"] is None)
        print(f"  done: {errs} questions without an answer", flush=True)


def usage_stats(model: str, tag: str) -> Dict[str, Any]:
    """Generator tokens per turn and per conversation, both pipelines, from the usage log."""
    out = {}
    for base in PIPELINES:
        path = OUT_DIR / f"{model}__{base}__usage_{tag}.jsonl"
        if not path.exists():
            continue
        calls = load(path)
        per_turn: Dict[str, np.ndarray] = defaultdict(lambda: np.zeros(4))
        dial_of = {}
        for c in calls:
            per_turn[c["example_id"]] += [c["input_tokens"], c["cached_tokens"], c["output_tokens"], c["reasoning_tokens"]]
            dial_of[c["example_id"]] = c["dialogue_id"]
        per_conv: Dict[str, np.ndarray] = defaultdict(lambda: np.zeros(4))
        for eid, v in per_turn.items():
            per_conv[dial_of[eid]] += v
        t = np.array(list(per_turn.values()))
        cv = np.array(list(per_conv.values()))
        p = PRICES[model]
        cost = lambda a: ((a[:, 0] - a[:, 1]) * p["input"] + a[:, 1] * p["cached_input"] + a[:, 2] * p["output"]) / 1e6
        stat = lambda x: {"mean": float(np.mean(x)), "median": float(np.median(x)), "p95": float(np.percentile(x, 95))}
        out[base] = {
            "turns": len(t), "conversations": len(cv), "calls": len(calls),
            "calls_per_turn": len(calls) / max(1, len(t)),
            "errors": sum(1 for c in calls if c["status"] != "ok"),
            "turn": {k: stat(t[:, i]) for i, k in enumerate(("input", "cached_input", "output", "reasoning"))},
            "conversation": {k: stat(cv[:, i]) for i, k in enumerate(("input", "cached_input", "output", "reasoning"))},
            "usd_per_1000_conversations": float(cost(cv).mean() * 1000),
            "usd_per_1000_conversations_no_cache": float(((cv[:, 0] * p["input"] + cv[:, 2] * p["output"]) / 1e6).mean() * 1000),
            "usd_per_turn": float(cost(t).mean()),
        }
    return out


def baseline_answers(base: str) -> Dict[str, Dict[str, Any]]:
    """gpt-5.4-nano G2 + abstain(G0) from the cached generator-input answers (the reported system)."""
    g0 = load(GEN_DIR / f"{base}__G0.jsonl")
    g2 = {r["example_id"]: r for r in load(GEN_DIR / f"{base}__G2_kall.jsonl")}
    out = {}
    for r in g0:
        a = ABSTAIN if is_abstention(r["model_answer"] or "") else g2[r["example_id"]]["model_answer"]
        out[r["example_id"]] = {**r, "model_answer": a}
    return out


def pilot_estimate(model: str) -> None:
    rows = load(GEN_DIR / "rag_rewrite_rerank_v2__G0.jsonl")
    n_full, n_conv = len(rows), len({r["dialogue_id"] for r in rows})
    lines = []
    for m in (model, BASELINE):
        s = usage_stats(m, "pilot")
        for base, st in s.items():
            full_usd = st["usd_per_turn"] * n_full
            lines.append(f"{m:13} {PIPELINES[base]:24} {st['turns']} turns: in/turn {st['turn']['input']['mean']:.0f} "
                         f"(cached {st['turn']['cached_input']['mean']:.0f}), out/turn {st['turn']['output']['mean']:.0f} "
                         f"(reasoning {st['turn']['reasoning']['mean']:.0f}); est. full split {n_full} turns: "
                         f"USD {full_usd:.2f}; USD {st['usd_per_1000_conversations']:.2f} per 1,000 conversations")
    print("\n".join(lines))


OTHERS = ("gpt-5-nano", "gpt-6-luna")
# Azure bill of the whole project for gpt-5.4-nano: EUR 34.56 for 164.62 M input and 11.56 M output tokens.
BILL_EUR, BILL_IN_M, BILL_OUT_M = 34.56, 164.62, 11.56


def _cached_call(model: str, prompt: str) -> Optional[Dict[str, Any]]:
    path = CACHE_ROOT / model / f"{hashlib.sha256(prompt.encode('utf-8')).hexdigest()}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _cost(model: str, u: Dict[str, Any]) -> float:
    p = PRICES[model]
    return ((u["input_tokens"] - u["cached_tokens"]) * p["input"] + u["cached_tokens"] * p["cached_input"]
            + u["output_tokens"] * p["output"]) / 1e6


def price_note() -> List[str]:
    p = PRICES[BASELINE]
    list_usd = BILL_IN_M * p["input"] + BILL_OUT_M * p["output"]
    all_cached_usd = BILL_IN_M * p["cached_input"] + BILL_OUT_M * p["output"]
    return ["## Prices", "",
            "All costs are USD list prices from the Azure Retail Prices API (prices.azure.com), Global Standard "
            "deployment, region East US 2, checked on 2026-10-21. The deployment type and region of the project's "
            "deployments are not confirmed, so the real prices can differ.", "",
            f"Check against the Azure bill of gpt-5.4-nano (EUR {BILL_EUR} for {BILL_IN_M} M input and "
            f"{BILL_OUT_M} M output tokens over the whole project, i.e. EUR {BILL_EUR / (BILL_IN_M + BILL_OUT_M):.3f} "
            f"per 1 M tokens on average): the same tokens at the list price cost USD {list_usd:.2f} if no input is "
            f"cached, and USD {all_cached_usd:.2f} if all input were cached. The bill (EUR {BILL_EUR}) lies inside "
            "this range; it does not say how much input was cached, and the EUR/USD rate is not applied here, so "
            "the bill neither confirms nor contradicts the list price exactly.", ""]


def quality_checks(base: str) -> List[str]:
    """F1 without refusals, and the mixed system (abstention of gpt-5.4-nano G0, answer of another model's G2)."""
    runs = {m: {r["example_id"]: r for r in load(OUT_DIR / f"{m}__{base}__answers_full.jsonl")} for m in MODELS}
    g0p = {r["example_id"]: r["prompt"] for r in load(GEN_DIR / f"{base}__G0.jsonl")}
    g2p = {r["example_id"]: r["prompt"] for r in load(GEN_DIR / f"{base}__G2_kall.jsonl")}
    ref = runs[BASELINE]
    ids = list(ref)
    f1 = lambda a, r: compute_metrics(a or "", r)["f1"]
    fmt = lambda t: f"{t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]"
    words = lambda a: len((a or "").split())
    answ = [i for i in ids if not ref[i]["is_unanswerable"]]
    out = ["### Answer quality without refusals (answerable questions)", "",
           "| Model | answered (not abstained) | F1 on them | mean words | F1 on the common subset | Δ vs 5.4-nano (common subset) |",
           "| :--- | ---: | :---: | :---: | :---: | :---: |"]
    answered = {m: [i for i in answ if runs[m][i]["model_answer"] and not is_abstention(runs[m][i]["model_answer"])]
                for m in MODELS}
    common = [i for i in answ if all(i in answered[m] for m in MODELS)]
    common_set = set(common)
    fb = [f1(ref[i]["model_answer"], ref[i]["reference_answer"]) for i in common]
    for m in MODELS:
        own = answered[m]
        f_own = np.mean([f1(runs[m][i]["model_answer"], runs[m][i]["reference_answer"]) for i in own])
        w = np.mean([words(runs[m][i]["model_answer"]) for i in own])
        fc = [f1(runs[m][i]["model_answer"], runs[m][i]["reference_answer"]) for i in common]
        d = "-" if m == BASELINE else fmt(paired_bootstrap_test(fc, fb))
        out.append(f"| {m} | {len(own)} of {len(answ)} | {f_own*100:.1f} | {w:.1f} | {np.mean(fc)*100:.1f} | {d} |")
    out += ["", f"Common subset: the {len(common)} answerable questions where all three models answered.", ""]

    out += ["### Mixed system: abstention from gpt-5.4-nano G0, answer from another model's G2", "",
            "Same G2 + abstain(G0) logic; G0 runs on gpt-5.4-nano and G2 on the other model. No new calls were "
            "made: the other model's G2 answer is in the cache only where its own G0 did not abstain, so questions "
            "where gpt-5.4-nano answers but the other model's G2 was never called are left out (counted below), and "
            "every comparison uses the same questions for both systems.", "",
            "| Answer model | n (left out) | F1 all | F1 answerable | F1 unanswerable | Δ all vs 5.4-nano | Δ answerable | "
            "abstain recall / false abstention | USD per 1,000 conv. |",
            "| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
    n_conv = len({ref[i]["dialogue_id"] for i in ids})
    g0_base = {i: _cached_call(BASELINE, g0p[i]) for i in ids}
    for m in OTHERS:
        final, cost, missing = {}, {}, 0
        g2_costs = []
        for i in ids:
            c0 = g0_base[i]
            a0 = c0["text"] if c0 else None
            if a0 is None:
                continue
            if is_abstention(a0):
                final[i], cost[i] = ABSTAIN, _cost(BASELINE, c0)
                continue
            if g2p[i] == g0p[i]:
                c2 = _cached_call(m, g0p[i])
            else:
                c2 = _cached_call(m, g2p[i])
            if not c2 or c2.get("text") is None:
                missing += 1
                continue
            final[i] = c2["text"]
            cost[i] = _cost(BASELINE, c0) + _cost(m, c2)
            g2_costs.append(_cost(m, c2))
        keep = [i for i in ids if i in final]
        f = np.array([f1(final[i], ref[i]["reference_answer"]) for i in keep])
        fb2 = np.array([f1(ref[i]["model_answer"], ref[i]["reference_answer"]) for i in keep])
        u = np.array([ref[i]["is_unanswerable"] for i in keep])
        ab = np.array([is_abstention(final[i]) for i in keep])
        d_all = paired_bootstrap_test(list(f), list(fb2))
        d_ans = paired_bootstrap_test(list(f[~u]), list(fb2[~u]))
        # cost per conversation over all questions: missing G2 calls counted at the mean G2 cost of this model
        per_conv: Dict[str, float] = defaultdict(float)
        mean_g2 = float(np.mean(g2_costs))
        for i in ids:
            c0 = g0_base[i]
            if i in cost:
                per_conv[ref[i]["dialogue_id"]] += cost[i]
            elif c0:
                per_conv[ref[i]["dialogue_id"]] += _cost(BASELINE, c0) + mean_g2
        usd = sum(per_conv.values()) / n_conv * 1000
        out.append(f"| {m} | {len(keep)} ({missing}) | {f.mean()*100:.1f} | {f[~u].mean()*100:.1f} | "
                   f"{f[u].mean()*100:.1f} | {fmt(d_all)} | {fmt(d_ans)} | "
                   f"{ab[u].mean()*100:.1f} / {ab[~u].mean()*100:.1f} | {usd:.2f} |")
    out += ["", "Cost: G0 on gpt-5.4-nano for every question plus G2 on the other model when G0 answers, from the "
            "recorded usage; the left-out G2 calls are counted at the mean G2 cost of that model.", ""]
    return out


def report() -> None:
    lines = ["# Generator models (validation, G2 + abstain(G0))", "",
             "Only the generator calls change model; rewrites, retrieval, graph facts and contexts are identical. "
             "All three models were run fresh on the full split with the same code and usage logging. "
             "Δ is the paired bootstrap difference in F1 to the fresh gpt-5.4-nano run on the same questions "
             "(questions without an answer from either run left out). The row 'gpt-5.4-nano, reported run' is "
             "the cached answers of the system in the reports (no usage recorded); comparing it with the fresh "
             "gpt-5.4-nano run shows the run-to-run variation of the same model. Tokens and cost are for the "
             "generator calls only (G0 always, G2 when G0 does not abstain); the rewriter stays on gpt-5.4-nano.", "",
             "Prices (USD per 1M tokens input / cached input / output, Global Standard, Azure Retail Prices API, "
             "eastus2, checked 2026-10-21): " + "; ".join(
                 f"{m} {p['input']} / {p['cached_input']} / {p['output']} ({p['meters']})" for m, p in PRICES.items()),
             "Cost uses the cached-input price for the input tokens the API reports as cached; 'no cache' is the "
             "same tokens all at the full input price.", ""]
    summary: Dict[str, Any] = {"prices_usd_per_1m": PRICES, "pipelines": {}}
    fmt = lambda t: f"{t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]"
    for base, label in PIPELINES.items():
        runs: Dict[str, Dict[str, Dict[str, Any]]] = {}
        stats: Dict[str, Any] = {}
        for model in MODELS:
            path = OUT_DIR / f"{model}__{base}__answers_full.jsonl"
            if path.exists():
                runs[model] = {r["example_id"]: r for r in load(path)}
                stats[model] = usage_stats(model, "full").get(base)
        runs["gpt-5.4-nano, reported run"] = baseline_answers(base)
        stats["gpt-5.4-nano, reported run"] = None
        ref = runs.get(BASELINE) or runs["gpt-5.4-nano, reported run"]
        lines += [f"## {label}", "",
                  "| Model | n | F1 all | F1 answerable | F1 unanswerable | Δ all vs 5.4-nano | Δ answerable | "
                  "abstain recall / false abstention | tokens/turn in (cached) / out (reasoning) | "
                  "tokens/conversation in / out (mean, median, p95) | USD per 1,000 conv. (no cache) |",
                  "| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
        summary["pipelines"][base] = {}
        for name, recs in runs.items():
            ids = [i for i in ref if i in recs and recs[i]["model_answer"] is not None and ref[i]["model_answer"] is not None]
            f = np.array([compute_metrics(recs[i]["model_answer"], recs[i]["reference_answer"])["f1"] for i in ids])
            fb = np.array([compute_metrics(ref[i]["model_answer"], ref[i]["reference_answer"])["f1"] for i in ids])
            u = np.array([recs[i]["is_unanswerable"] for i in ids])
            ab = np.array([is_abstention(recs[i]["model_answer"]) for i in ids])
            st = stats[name]
            e: Dict[str, Any] = {"n": len(ids), "missing": len(recs) - len(ids), "f1": float(f.mean()),
                                 "f1_answerable": float(f[~u].mean()), "f1_unanswerable": float(f[u].mean()),
                                 "abstain_recall": float(ab[u].mean()), "false_abstention": float(ab[~u].mean()),
                                 "usage": st}
            d_all = d_ans = "-"
            if recs is not ref:
                e["delta_all"] = paired_bootstrap_test(list(f), list(fb))
                e["delta_answerable"] = paired_bootstrap_test(list(f[~u]), list(fb[~u]))
                d_all, d_ans = fmt(e["delta_all"]), fmt(e["delta_answerable"])
            if st:
                tt, cc = st["turn"], st["conversation"]
                tok = (f"{tt['input']['mean']:.0f} ({tt['cached_input']['mean']:.0f}) / "
                       f"{tt['output']['mean']:.0f} ({tt['reasoning']['mean']:.0f})")
                conv = (f"{cc['input']['mean']:.0f}, {cc['input']['median']:.0f}, {cc['input']['p95']:.0f} / "
                        f"{cc['output']['mean']:.0f}, {cc['output']['median']:.0f}, {cc['output']['p95']:.0f}")
                usd = f"{st['usd_per_1000_conversations']:.2f} ({st['usd_per_1000_conversations_no_cache']:.2f})"
            else:
                tok = conv = usd = "-"
            lines.append(f"| {name} | {len(ids)} | {e['f1']*100:.1f} | {e['f1_answerable']*100:.1f} | "
                         f"{e['f1_unanswerable']*100:.1f} | {d_all} | {d_ans} | "
                         f"{e['abstain_recall']*100:.1f} / {e['false_abstention']*100:.1f} | {tok} | {conv} | {usd} |")
            summary["pipelines"][base][name] = e
        lines.append("")
        lines += quality_checks(base)
    lines += price_note()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", choices=list(MODELS), required=True)
    r.add_argument("--pilot", action="store_true", help="only the pilot conversations (>= 500 questions)")
    r.add_argument("--workers", type=int, default=12)
    e = sub.add_parser("estimate")
    e.add_argument("--model", choices=list(MODELS), required=True)
    sub.add_parser("report")
    args = parser.parse_args()
    if args.cmd == "run":
        run(args.model, args.pilot, args.workers)
    elif args.cmd == "estimate":
        pilot_estimate(args.model)
    else:
        report()


if __name__ == "__main__":
    main()
