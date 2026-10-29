"""Step 8, agent with a sufficiency check (validation and dev-500; the test split is not used here).

    A1  one check on (rewritten query, top-5 sections, facts); if insufficient, one extra round: a new search
        query, retrieval + reranking, facts of the newly linked entities, answer or refuse. Sufficient questions
        keep the answer of E (with citations, from the cache).
    A2  tool-calling agent (search_passages, get_entity_facts, answer, refuse), at most 3 tool calls.

Baseline E: G2 + abstain(G0) with the citation prompt (experiments/results/validation/sources/cite_*.jsonl).

    python experiments/agent.py smoke-a2                       # 10 dev-500 questions
    python experiments/agent.py a1 --limit 100 --dry-run       # calls and cost before the run
    python experiments/agent.py a1 --split dev500 [--limit N] [--max-usd X]
    python experiments/agent.py report --split dev500
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import experiments.graph_rag as gr
import experiments.sources as S
from experiments.evaluate_diagnostics import paired_bootstrap_test
from experiments.generator_input import TAIL, build_prompt
from src.agents.loop import ABSTAIN, run_a2, tool_prompt
from src.agents.sufficiency import check_prompt, parse_check
from src.agents.world import World
from src.evaluation.metrics import compute_metrics, is_abstention
from src.llm import LLMCache, LLMClient, call_meta, generate_batch
from src.llm.client import DEFAULT_USAGE_LOG

RESULTS = PROJECT_ROOT / "experiments" / "results"
CACHE_DIR = PROJECT_ROOT / "experiments" / "cache"
DEV_IDS = PROJECT_ROOT / "data" / "dev_500_ids.json"
WORKERS = 12
CHUNK = 100
PRICE_IN, PRICE_OUT = 0.20e-6, 1.25e-6  # gpt-5.4-nano list price per token, no cached input
ENC = tiktoken.get_encoding("o200k_base")


def ntok(text: str) -> int:
    return len(ENC.encode(text or "", disallowed_special=()))


def cost(tin: float, tout: float) -> float:
    return tin * PRICE_IN + tout * PRICE_OUT


def out_dir(split: str) -> Path:
    d = RESULTS / ("dev_500" if split == "dev500" else split) / "agent"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Spend:
    """Spend of this process from the usage log (new calls only, list price, no cached input)."""

    def __init__(self, pipeline: str, cap: float):
        self.t0, self.pipeline, self.cap = time.time(), pipeline, cap

    def total(self) -> float:
        tot = 0.0
        for line in open(DEFAULT_USAGE_LOG, encoding="utf-8"):
            r = json.loads(line)
            if r["t"] >= self.t0 and r.get("pipeline") == self.pipeline and not r["cache_hit"]:
                tot += cost(r.get("input_tokens") or 0, r.get("output_tokens") or 0)
        return tot

    def check(self) -> None:
        if self.total() > self.cap:
            raise SystemExit(f"stopped: spend USD {self.total():.2f} passed the cap of USD {self.cap:.2f}")


def batch(client, cache, spend: Spend, prompts: List[str], metas: List[Dict]) -> List[Any]:
    """generate_batch in chunks, checking the spend cap between chunks."""
    out = []
    for lo in range(0, len(prompts), CHUNK):
        out += generate_batch(client, prompts[lo:lo + CHUNK], cache=cache, max_workers=WORKERS, verbose=False,
                              metas=metas[lo:lo + CHUNK])
        spend.check()
    return out


def uncached(cache: LLMCache, prompts: List[str]) -> List[str]:
    return [p for p in dict.fromkeys(prompts) if not cache._path(p).exists()]


def dev_ids() -> List[str]:
    return json.loads(DEV_IDS.read_text())


def e_cite(split: str) -> Dict[str, Dict[str, Any]]:
    return {r["example_id"]: r for r in S.load(S.OUT / f"cite_{split}.jsonl")}


# ---------------------------------------------------------------------------- prompts
def g0_prompt(ex: Dict, context: str) -> str:
    head = gr.template().format(context=context, question="\x00").split("\n\nCustomer: \x00")[0]
    return head + TAIL.format(question=ex["question"])


def g2_cite_prompt(ex: Dict, query: str, context: str) -> str:
    head = S.cite_template().format(context=context, question="\x00").split("\n\nCustomer: \x00")[0]
    return build_prompt(head, ex, query, "G2", None)


def a2_prompt(ex: Dict, query: str, context: str) -> str:
    head = tool_prompt(gr.template()).format(context=context, question="\x00").split("\n\nCustomer: \x00")[0]
    return build_prompt(head, ex, query, "G2", None)


# ---------------------------------------------------------------------------- A2 smoke test
def smoke_a2(n: int = 10) -> None:
    ids = dev_ids()[:n]
    world = World("dev500")
    turns = world.turns(ids)
    exs = gr.examples()
    client, cache, spend = LLMClient(), LLMCache(CACHE_DIR), Spend("agent_a2_smoke", 0.5)
    rows = []
    for i in ids:
        t = turns[i]
        meta = call_meta(exs[i], "a2-turn", "agent_a2_smoke")
        res = run_a2(world, client, cache, t, a2_prompt(exs[i], t.query, world.render(t.sections, t.facts, cite=True)), meta)
        spend.check()
        f = res["final"]
        ans = ABSTAIN if f["kind"] == "refuse" else f["text"] + (f" [{', '.join(f['citations'])}]" if f["citations"] else "")
        rows.append({"example_id": i, "question": exs[i]["question"], "n_tools": res["n_tools"], "trace": res["trace"],
                     "final": f, "answer": ans, "reference_answer": exs[i]["reference_answer"]})
        log(f"{i}: {res['n_tools']} tools {[(x['tool'], x.get('arg')) for x in res['trace']]} -> {f['kind']}: {ans[:90]}")
    path = out_dir("dev500") / "a2_smoke.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    log(f"{n} questions, spend USD {spend.total():.3f}, written to {path.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------- A1
def run_a1(split: str, limit: int, dry_run: bool, max_usd: float, tag: str) -> None:
    ids = dev_ids() if split == "dev500" else list(S.e_system())
    ids = ids[:limit] if limit else ids
    exs, E, EC = gr.examples(), S.e_system(), e_cite("dev500" if split == "dev500" else "validation")
    world = World(split)
    turns = world.turns(ids)
    bad = [i for i in ids if world.render(turns[i].sections, turns[i].facts) != E[i]["context"]]
    assert not bad, f"{len(bad)} rebuilt contexts differ from E's, e.g. {bad[0]}"
    client, cache, spend = LLMClient(), LLMCache(CACHE_DIR), Spend("agent_a1", max_usd)

    # 1. check on every question
    ctx_cite = {i: world.render(turns[i].sections, turns[i].facts, cite=True) for i in ids}
    prompts = [check_prompt(turns[i].query, ctx_cite[i]) for i in ids]
    new = uncached(cache, prompts)
    tin = sum(ntok(p) for p in new)
    est = cost(tin, 70 * len(new))
    log(f"check: {len(ids)} questions, {len(new)} new calls, {tin:,} input tokens, ~USD {est:.2f}")
    if dry_run:
        p = 0.4
        n2 = p * len(ids)
        log(f"extra round (assuming {p:.0%} insufficient): ~{n2:.0f} questions x (G0 + G2 + check2) = ~{n2 * 3.9:.0f} calls, "
            f"~USD {n2 * (2 * 4600 * PRICE_IN + 100 * PRICE_OUT + 4600 * PRICE_IN + 70 * PRICE_OUT):.2f}")
        return
    checks = batch(client, cache, spend, prompts, [call_meta(exs[i], "check", "agent_a1") for i in ids])
    chk = {i: parse_check(a or "") | {"raw": a} for i, (a, _) in zip(ids, checks)}
    rnd = [i for i in ids if chk[i]["ok"] and not chk[i]["sufficient"]]
    log(f"check done: {sum(not chk[i]['ok'] for i in ids)} parse failures, {len(rnd)} of {len(ids)} questions "
        f"({len(rnd) / len(ids):.1%}) take the extra round; spend USD {spend.total():.2f}")

    # 2. the extra round (retrieval is local)
    info: Dict[str, Dict[str, Any]] = {}
    if rnd:
        q2 = [chk[i]["search_query"] for i in rnd]
        ranked = world.search(q2)
        embs = world.linker.encode(q2)
        for i, q, r, emb in zip(rnd, q2, ranked, embs):
            t = turns[i]
            new_secs = world.add_sections(t, r)
            new_facts = world.add_facts(t, world.new_entities(t, world.kg.link(q, emb)), emb)
            union, facts = t.sections + new_secs, t.facts + new_facts
            info[i] = {"new_top5": [s["section_id"] for s in r[:5]], "new_sections": [s["section_id"] for s in new_secs],
                       "union": [s["section_id"] for s in union], "n_new_facts": len(new_facts),
                       "gold_new_top5": bool(t.gold & {s["section_id"] for s in r[:5]}),
                       "after": world.gold_in_context(t, union, facts),
                       "ctx": world.render(union, facts), "ctx_cite": world.render(union, facts, cite=True)}
        # 3. answers on the new context: G0 (abstention), G2 with citations, second check
        g0p = [g0_prompt(exs[i], info[i]["ctx"]) for i in rnd]
        g2p = [g2_cite_prompt(exs[i], turns[i].query, info[i]["ctx_cite"]) for i in rnd]
        c2p = [check_prompt(turns[i].query, info[i]["ctx_cite"]) for i in rnd]
        new = uncached(cache, g0p + g2p + c2p)
        log(f"round 2: {len(rnd)} questions, {len(new)} new calls, {sum(ntok(p) for p in new):,} input tokens")
        a0 = batch(client, cache, spend, g0p, [call_meta(exs[i], "G0", "agent_a1") for i in rnd])
        a2 = batch(client, cache, spend, g2p, [call_meta(exs[i], "G2-cite", "agent_a1") for i in rnd])
        a3 = batch(client, cache, spend, c2p, [call_meta(exs[i], "check2", "agent_a1") for i in rnd])
        for k, i in enumerate(rnd):
            info[i].update({"g0_prompt": g0p[k], "g0_answer": a0[k][0], "g2_prompt": g2p[k], "g2_answer": a2[k][0],
                            "check2": parse_check(a3[k][0] or "") | {"raw": a3[k][0]}, "check2_prompt": c2p[k]})

    # 4. records: both refusal decisions side by side
    rows = []
    for i in ids:
        t, c, ec = turns[i], chk[i], EC[i]
        base = ec["model_answer"]
        row = {"example_id": i, "is_unanswerable": exs[i]["is_unanswerable"], "reference_answer": exs[i]["reference_answer"],
               "check": {k: c[k] for k in ("ok", "sufficient", "missing", "search_query")}, "check_prompt_tokens": ntok(check_prompt(t.query, ctx_cite[i])),
               "check_output_tokens": ntok(c["raw"]), "took_round": i in info, "gold_before": world.gold_in_context(t),
               "gold_top5": bool(t.gold & set(t.section_ids())), "e_answer": base, "a1_g0": base, "a1_own": base}
        if i in info:
            n = info[i]
            g0, g2, c2 = n["g0_answer"], n["g2_answer"], n["check2"]
            row["a1_g0"] = ABSTAIN if (g0 is None or is_abstention(g0)) else g2
            row["a1_own"] = ABSTAIN if (c2["ok"] and not c2["sufficient"]) else g2
            row.update({k: n[k] for k in ("new_top5", "new_sections", "union", "n_new_facts", "gold_new_top5", "after")})
            row["check2"] = {k: c2[k] for k in ("ok", "sufficient", "missing", "search_query")}
            row["round_tokens"] = {"g0": [ntok(n["g0_prompt"]), ntok(g0)], "g2": [ntok(n["g2_prompt"]), ntok(g2)],
                                   "check2": [ntok(n["check2_prompt"]), ntok(c2["raw"])]}
        rows.append(row)
    path = out_dir(split) / f"a1{tag}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    log(f"{len(rows)} records written to {path.relative_to(PROJECT_ROOT)}; spend this run USD {spend.total():.2f}")


# ---------------------------------------------------------------------------- report
def f1_of(ans: str, ref: str) -> float:
    return compute_metrics(S.strip_citations(ans or ""), ref)["f1"]


def youden(y: np.ndarray, pred: np.ndarray, n_boot: int = 1000, seed: int = 42) -> Dict[str, float]:
    def j(yy, pp):
        pos, neg = yy.sum(), (~yy).sum()
        return (pp[yy].sum() / pos if pos else 0.0) + ((~pp)[~yy].sum() / neg if neg else 0.0) - 1
    rng = np.random.default_rng(seed)
    boots = [j(y[s], pred[s]) for s in (rng.integers(0, len(y), len(y)) for _ in range(n_boot))]
    return {"J": float(j(y, pred)), "ci_low": float(np.percentile(boots, 2.5)), "ci_high": float(np.percentile(boots, 97.5))}


def report(split: str, tag: str) -> None:
    rows = [json.loads(l) for l in open(out_dir(split) / f"a1{tag}.jsonl", encoding="utf-8")]
    E = S.e_system()
    E_tok = {}  # tokens of E's own calls (G0 plain always, G2 with citations when G0 did not abstain)
    g0 = {r["example_id"]: r for r in S.load(S.GEN / "step4_plus_facts__G0.jsonl")}
    ec = e_cite("dev500" if split == "dev500" else "validation")
    n = len(rows)
    res: Dict[str, Any] = {"split": split, "n": n}
    sub = lambda keep: [k for k, r in enumerate(rows) if keep(r)]
    hit = lambda r: r["gold_top5"]
    sets = {"all": sub(lambda r: True), "answerable": sub(lambda r: not r["is_unanswerable"]),
            "unanswerable": sub(lambda r: r["is_unanswerable"]),
            "passages-miss": sub(lambda r: not r["is_unanswerable"] and not hit(r)),
            "passages-hit": sub(lambda r: not r["is_unanswerable"] and hit(r)),
            "took round": sub(lambda r: r["took_round"])}
    ref = [r["reference_answer"] for r in rows]
    systems = {"E": "e_answer", "A1 (abstain G0)": "a1_g0", "A1 (own refusal)": "a1_own"}
    res["f1"] = {name: {s: float(np.mean([f1_of(rows[k][key], ref[k]) for k in ks])) for s, ks in sets.items() if ks}
                 for name, key in systems.items()}
    res["set_sizes"] = {s: len(ks) for s, ks in sets.items()}
    res["delta_vs_E"] = {}
    for name, key in list(systems.items())[1:]:
        res["delta_vs_E"][name] = {}
        for s in ("all", "answerable", "passages-miss", "passages-hit", "took round"):
            ks = sets[s]
            if ks:
                res["delta_vs_E"][name][s] = paired_bootstrap_test([f1_of(rows[k][key], ref[k]) for k in ks],
                                                                    [f1_of(rows[k]["e_answer"], ref[k]) for k in ks])
    res["abstention"] = {name: {"false_abstention": float(np.mean([is_abstention(S.strip_citations(rows[k][key] or "")) for k in sets["answerable"]])),
                                "abstain_recall": float(np.mean([is_abstention(S.strip_citations(rows[k][key] or "")) for k in sets["unanswerable"]]))}
                         for name, key in systems.items()}
    # the share that takes the round, parse failures, retrieval after the round
    took = [r for r in rows if r["took_round"]]
    res["round_share"] = len(took) / n
    res["parse_failures"] = sum(not r["check"]["ok"] for r in rows)
    ans_took = [r for r in took if not r["is_unanswerable"]]
    if took:
        res["round"] = {"n": len(took), "n_answerable": len(ans_took),
                        "mean_new_sections": float(np.mean([len(r["new_sections"]) for r in took])),
                        "mean_new_facts": float(np.mean([r["n_new_facts"] for r in took])),
                        "R@5_E_top5": float(np.mean([r["gold_top5"] for r in ans_took])) if ans_took else None,
                        "R@5_new_query": float(np.mean([r["gold_new_top5"] for r in ans_took])) if ans_took else None,
                        "R@10_union_passages": float(np.mean([bool(set(r["union"]) & set(rows_gold(split, r["example_id"]))) for r in ans_took])) if ans_took else None,
                        "gold_in_context_before_broad": float(np.mean([r["gold_before"]["broad"] for r in ans_took])) if ans_took else None,
                        "gold_in_context_after_broad": float(np.mean([r["after"]["broad"] for r in ans_took])) if ans_took else None,
                        "second_check_insufficient": float(np.mean([r["check2"]["ok"] and not r["check2"]["sufficient"] for r in took]))}
    # classifier: the check against 'gold section in context' (answerable questions)
    clf = {}
    ans = [r for r in rows if not r["is_unanswerable"]]
    pred = np.array([r["check"]["sufficient"] for r in ans])
    for kind in ("broad", "strict"):
        y = np.array([r["gold_before"][kind] for r in ans])
        tp, fp, fn, tn = int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum()), int((~pred & ~y).sum())
        clf[kind] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "base_rate_gold_in_context": float(y.mean()),
                     "precision_sufficient": tp / max(1, tp + fp), "recall_sufficient": tp / max(1, tp + fn),
                     "precision_insufficient": tn / max(1, tn + fn), "recall_insufficient": tn / max(1, tn + fp),
                     **youden(y, pred)}
    res["classifier"] = clf
    un = [r for r in rows if r["is_unanswerable"]]
    res["unanswerable_called_insufficient"] = {"n": len(un), "share": float(np.mean([not r["check"]["sufficient"] for r in un])) if un else None}
    # tokens and cost per turn (the rewrite is the same for all and left out)
    def e_calls(i):
        g = g0[i]
        t = ntok(g["prompt"]) + ntok(g["model_answer"] or ""), 0
        tin, tout = ntok(g["prompt"]), ntok(g["model_answer"] or "")
        if ec[i]["prompt"]:
            tin, tout = tin + ntok(ec[i]["prompt"]), tout + ntok(ec[i]["raw_answer"] or "")
        return tin, tout, 2 if ec[i]["prompt"] else 1
    tot = {"E": [0, 0, 0], "A1 (abstain G0)": [0, 0, 0], "A1 (own refusal)": [0, 0, 0]}
    for r in rows:
        ei, eo, en = e_calls(r["example_id"])
        ci, co = r["check_prompt_tokens"], r["check_output_tokens"]
        tot["E"] = [a + b for a, b in zip(tot["E"], (ei, eo, en))]
        if not r["took_round"]:
            add = (ci + ei, co + eo, 1 + en)
            tot["A1 (abstain G0)"] = [a + b for a, b in zip(tot["A1 (abstain G0)"], add)]
            tot["A1 (own refusal)"] = [a + b for a, b in zip(tot["A1 (own refusal)"], add)]
        else:
            t = r["round_tokens"]
            g0_ok = r["a1_g0"] is not None
            a = (ci + t["g0"][0] + (t["g2"][0] if not is_abstention(r["a1_g0"] or "") else 0),
                 co + t["g0"][1] + (t["g2"][1] if not is_abstention(r["a1_g0"] or "") else 0),
                 1 + 1 + (0 if is_abstention(r["a1_g0"] or "") else 1))
            b = (ci + t["g2"][0] + t["check2"][0], co + t["g2"][1] + t["check2"][1], 3)
            tot["A1 (abstain G0)"] = [x + y for x, y in zip(tot["A1 (abstain G0)"], a)]
            tot["A1 (own refusal)"] = [x + y for x, y in zip(tot["A1 (own refusal)"], b)]
    res["per_turn"] = {k: {"in": v[0] / n, "out": v[1] / n, "calls": v[2] / n, "usd_per_1000": 1000 * cost(v[0], v[1]) / n}
                       for k, v in tot.items()}
    path = out_dir(split) / f"a1{tag}_summary.json"
    path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    log(f"summary written to {path.relative_to(PROJECT_ROOT)}")
    print(json.dumps(res, indent=2))


_GOLD: Dict[str, Dict[str, list]] = {}


def rows_gold(split: str, example_id: str) -> list:
    key = "dev500" if split == "dev500" else "validation"
    if key not in _GOLD:
        from src.kg_rag.queries import load_step4
        _GOLD[key] = {i: r["gold_sections"] for i, r in load_step4(key)["records"].items()}
    return _GOLD[key][example_id]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["smoke-a2", "a1", "report"])
    ap.add_argument("--split", choices=["dev500", "validation"], default="dev500")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=2.0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if a.command == "smoke-a2":
        smoke_a2()
    elif a.command == "a1":
        run_a1(a.split, a.limit, a.dry_run, a.max_usd, a.tag)
    else:
        report(a.split, a.tag)


if __name__ == "__main__":
    main()
