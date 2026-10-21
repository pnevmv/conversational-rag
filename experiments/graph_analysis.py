"""When does the graph help? Analysis of cached outputs only (no LLM calls), full validation split.

Systems (gpt-5.4-nano, G2 + abstain(G0), cached answers of experiments/generator_input.py):
    P  passages                (rag_rewrite_rerank_v2)
    E  passages + graph facts  (step4_plus_facts)
    B  graph facts only        (kg_facts; run only with the current user turn, G0, no history)

1. d = F1(E) - F1(P) per question, broken down by question type (groups of >= 100 questions).
2. Oracle routers: best of P / E / B and best of P / E per question.
3. A cheap router between P and E with features available before generation, fitted on dev-500
   and evaluated on the rest of the validation split.

    python experiments/graph_analysis.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evaluate_diagnostics import paired_bootstrap_test
from experiments.generator_input import dialogue_acts
from src.data.loader import load_qa_pairs
from src.evaluation.metrics import compute_metrics, is_abstention
from src.kg_rag.queries import load_step4

VAL = PROJECT_ROOT / "experiments" / "results" / "validation"
GEN = VAL / "generator_input"
OUT = VAL / "graph_analysis"
DEV_IDS = PROJECT_ROOT / "data" / "dev_500_ids.json"
ENTITIES = PROJECT_ROOT / "experiments" / "kg_rag" / "entities_full.json"
ABSTAIN = "Unfortunately, no relevant information is found."
MIN_GROUP = 100


def load(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def g2_abstain_g0(base: str) -> Dict[str, str]:
    g0 = load(GEN / f"{base}__G0.jsonl")
    g2 = {r["example_id"]: r["model_answer"] for r in load(GEN / f"{base}__G2_kall.jsonl")}
    return {r["example_id"]: ABSTAIN if is_abstention(r["model_answer"] or "") else g2[r["example_id"]] for r in g0}


def f1(a: str, ref: str) -> float:
    return compute_metrics(a or "", ref)["f1"]


def fact_overlap(context: str) -> float:
    """Share of facts whose evidence section is one of the 5 passages in the same prompt."""
    ctx, _, facts = context.partition("\n\nFacts:\n")
    heads = set(re.findall(r"^\[\d+\] (.+)$", ctx, flags=re.M))
    ev = re.findall(r'^    Evidence: ".*" \((.+)\)$', facts, flags=re.M)
    return float(np.mean([e in heads for e in ev])) if ev else 0.0


def names_entity(question: str, linked: List[Dict[str, Any]], forms: Dict[str, List[str]]) -> bool:
    q = " " + re.sub(r"[^a-z0-9]+", " ", question.lower()) + " "
    for l in linked:
        for f in forms.get(l["entity_id"], [l["name"]]):
            f = re.sub(r"[^a-z0-9]+", " ", f.lower()).strip()
            if len(f) >= 3 and f" {f} " in q:
                return True
    return False


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    examples = {ex["example_id"]: ex for ex in load_qa_pairs(split="validation", max_examples=None)}
    das = dialogue_acts("validation")
    p_ans, e_ans = g2_abstain_g0("rag_rewrite_rerank_v2"), g2_abstain_g0("step4_plus_facts")
    e_rec = {r["example_id"]: r for r in load(VAL / "step4_plus_facts.jsonl")}
    p_rec = {r["example_id"]: r for r in load(VAL / "rag_rewrite_rerank_v2.jsonl")}
    b_rec = {r["example_id"]: r for r in load(VAL / "kg_facts.jsonl")}
    s4 = load_step4("validation")["records"]
    forms = {e["entity_id"]: e["forms"] for e in json.load(open(ENTITIES, encoding="utf-8"))}
    dev = set(json.loads(DEV_IDS.read_text()))

    ids = [i for i in e_rec if i in p_ans and i in e_ans and b_rec[i]["model_answer"] is not None]
    rows = []
    for i in ids:
        ex, er, pr = examples[i], e_rec[i], p_rec[i]
        ref = ex["reference_answer"]
        ranking = s4[i]["step4_ranking"]
        rows.append({
            "id": i, "dev": i in dev,
            "fP": f1(p_ans[i], ref), "fE": f1(e_ans[i], ref), "fB": f1(b_rec[i]["model_answer"], ref),
            "agent_da": das[i]["agent_da"], "user_da": das[i]["user_da"], "domain": ex["domain"],
            "first": not ex["dialogue_history"], "switch": bool(ex.get("is_doc_switch")),
            "hit": pr["recall_at_5"] > 0, "fact_gold": er["facts_context_recall"] > 0,
            "n_facts": er["n_facts"], "names_entity": names_entity(ex["question"], er["linked_entities"], forms),
            "unans": ex["is_unanswerable"],
            # features available before generation
            "top1": ranking[0]["reranker_score"], "gap12": ranking[0]["reranker_score"] - ranking[1]["reranker_score"],
            "top5_mean": float(np.mean([r["reranker_score"] for r in ranking[:5]])),
            "overlap": fact_overlap(er["context"]),
            "deg_mean": float(np.mean([l["degree"] for l in er["linked_entities"]])),
            "turn": ex["turn_id"], "hist": len(ex["dialogue_history"]), "q_len": len(ex["question"].split()),
        })
    for r in rows:
        r["d"] = r["fE"] - r["fP"]
    n = len(rows)
    fmt = lambda t: f"{t['mean_diff']*100:+.1f} [{t['ci_low']*100:.1f}, {t['ci_high']*100:.1f}]"

    def group_table(title: str, key: Callable[[Dict], Any]) -> List[str]:
        groups: Dict[Any, List[Dict]] = defaultdict(list)
        for r in rows:
            groups[key(r)].append(r)
        out = [f"**{title}**", "", "| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |",
               "| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |"]
        for g, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(rs) < MIN_GROUP:
                continue
            t = paired_bootstrap_test([r["fE"] for r in rs], [r["fP"] for r in rs])
            out.append(f"| {g} | {len(rs)} | {np.mean([r['fP'] for r in rs])*100:.1f} | "
                       f"{np.mean([r['fE'] for r in rs])*100:.1f} | {np.mean([r['fB'] for r in rs])*100:.1f} | {fmt(t)} | "
                       f"{np.mean([r['d'] > 0 for r in rs])*100:.0f}% | {np.mean([r['d'] < 0 for r in rs])*100:.0f}% |")
        return out + [""]

    lines = ["# When does the graph help? (validation, cached outputs)", "",
             f"P = passages, E = passages + graph facts, both with the conversational generator (G2 + abstain(G0), "
             f"gpt-5.4-nano, cached answers); B = graph facts only, which exists only with the current user turn (G0, no "
             f"dialogue history). d = F1(E) - F1(P) per question, mean in points with a paired bootstrap 95% interval; "
             f"d > 0 / d < 0 are the shares of questions where E is better / worse. Groups with fewer than {MIN_GROUP} "
             f"questions are not shown. n = {n} questions, no new LLM calls.", "",
             f"Overall: F1 P {np.mean([r['fP'] for r in rows])*100:.1f}, E {np.mean([r['fE'] for r in rows])*100:.1f}, "
             f"B {np.mean([r['fB'] for r in rows])*100:.1f}; d = "
             f"{fmt(paired_bootstrap_test([r['fE'] for r in rows], [r['fP'] for r in rows]))}; "
             f"E better on {np.mean([r['d'] > 0 for r in rows])*100:.0f}%, worse on "
             f"{np.mean([r['d'] < 0 for r in rows])*100:.0f}%, equal on {np.mean([r['d'] == 0 for r in rows])*100:.0f}%.", "",
             "## 1. Where the graph facts help", ""]
    lines += group_table("Dialogue act of the reference agent turn", lambda r: r["agent_da"])
    lines += group_table("Dialogue act of the user turn", lambda r: r["user_da"])
    lines += group_table("Domain", lambda r: r["domain"])
    lines += group_table("Position", lambda r: "first turn" if r["first"] else "follow-up")
    lines += group_table("Document", lambda r: "doc switch" if r["switch"] else "same document")
    lines += group_table("Passage retrieval (gold section in the top 5)", lambda r: "hit" if r["hit"] else "miss")
    lines += group_table("At least one fact from a gold section", lambda r: "yes" if r["fact_gold"] else "no")
    lines += group_table("Hit and gold fact", lambda r: f"{'hit' if r['hit'] else 'miss'}, gold fact {'yes' if r['fact_gold'] else 'no'}")
    lines += group_table("Number of facts", lambda r: "30" if r["n_facts"] >= 30 else ("20-29" if r["n_facts"] >= 20 else "< 20"))
    lines += group_table("Question names a linked entity (string match)", lambda r: "yes" if r["names_entity"] else "no")
    lines += group_table("Answerable", lambda r: "unanswerable" if r["unans"] else "answerable")
    lines.append("All questions have 10 linked entities, so the number of linked entities does not split them.\n")

    # 2. oracle routers
    fP, fE, fB = (np.array([r[k] for r in rows]) for k in ("fP", "fE", "fB"))
    o2, o3 = np.maximum(fP, fE), np.maximum(np.maximum(fP, fE), fB)
    lines += ["## 2. Oracle routers", "",
              "Per question the better system is chosen with the reference answer, so this is an upper bound, not a "
              "usable system. Part of the gain is noise: two runs of the same system also differ per question.", "",
              "| Router | F1 | gain over E [95% CI] |", "| :--- | :---: | :---: |",
              f"| always P | {fP.mean()*100:.1f} | {fmt(paired_bootstrap_test(list(fP), list(fE)))} |",
              f"| always E | {fE.mean()*100:.1f} | - |",
              f"| oracle P / E | {o2.mean()*100:.1f} | {fmt(paired_bootstrap_test(list(o2), list(fE)))} |",
              f"| oracle P / E / B | {o3.mean()*100:.1f} | {fmt(paired_bootstrap_test(list(o3), list(fE)))} |", ""]
    # noise reference: the best of two runs of the same system E (cached run and the fresh run of
    # experiments/model_comparison.py), which can only gain through run-to-run variation
    fresh = VAL / "model_comparison" / "gpt-5.4-nano__step4_plus_facts__answers_full.jsonl"
    if fresh.exists():
        e2 = {r["example_id"]: r["model_answer"] for r in load(fresh)}
        fE2 = np.array([f1(e2.get(r["id"]), examples[r["id"]]["reference_answer"]) for r in rows])
        on = np.maximum(fE, fE2)
        lines.insert(len(lines) - 1, f"| oracle between two runs of E (noise reference) | {on.mean()*100:.1f} | "
                     f"{fmt(paired_bootstrap_test(list(on), list(fE)))} |")
        noise_gain = (on.mean() - fE.mean()) * 100
    else:
        noise_gain = 0.0
    oracle_gain = (o2.mean() - fE.mean()) * 100

    # 3. cheap router P vs E
    feats = ["top1", "gap12", "top5_mean", "overlap", "deg_mean", "n_facts", "turn", "hist", "q_len", "first", "switch",
             "names_entity"]
    lines += ["## 3. A cheap router between P and E", ""]
    if oracle_gain <= 1.0:
        lines += [f"The oracle P / E gain over E is {oracle_gain:.1f} points, not clearly above 1, so no router was "
                  "fitted.", ""]
    else:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        X = np.array([[float(r[f]) for f in feats] for r in rows])
        is_dev = np.array([r["dev"] for r in rows])
        d = np.array([r["d"] for r in rows])
        y = (d > 0).astype(int)
        train = is_dev & (d != 0)
        scaler = StandardScaler().fit(X[is_dev])
        clf = LogisticRegression(max_iter=1000).fit(scaler.transform(X[train]), y[train])
        prob = clf.predict_proba(scaler.transform(X))[:, 1]
        test = ~is_dev
        # threshold on the probability of E being better, chosen on dev-500
        cands = np.unique(np.round(prob[is_dev], 3))
        best_t = max(cands, key=lambda t: np.where(prob[is_dev] >= t, fE[is_dev], fP[is_dev]).mean())
        routed = np.where(prob >= best_t, fE, fP)
        # single-feature threshold: use E when the fact evidence overlaps the passages
        best_single = None
        for f in ["overlap", "top1", "n_facts"]:
            col = X[:, feats.index(f)]
            for t in np.unique(np.round(col[is_dev], 3)):
                for sign in (1, -1):
                    use_e = (sign * (col - t)) >= 0
                    s = np.where(use_e, fE, fP)[is_dev].mean()
                    if best_single is None or s > best_single[0]:
                        best_single = (s, f, t, sign)
        _, sf, st, ss = best_single
        col = X[:, feats.index(sf)]
        routed1 = np.where((ss * (col - st)) >= 0, fE, fP)
        coef = sorted(zip(feats, clf.coef_[0]), key=lambda kv: -abs(kv[1]))
        nt = int(test.sum())
        lines += [f"Fitted on the {int(is_dev.sum())} dev-500 questions (labels: E better than P, ties left out), "
                  f"evaluated on the other {nt} validation questions. Features available before generation: "
                  + ", ".join(feats) + ". top1/gap12/top5_mean are cross-encoder scores of the passage ranking, "
                  "overlap is the share of facts whose evidence section is among the 5 passages, deg_mean the mean "
                  "degree of the linked entities.", "",
                  "| Router (held-out validation) | F1 | vs always E [95% CI] | share routed to E |",
                  "| :--- | :---: | :---: | :---: |",
                  f"| always P | {fP[test].mean()*100:.1f} | {fmt(paired_bootstrap_test(list(fP[test]), list(fE[test])))} | 0% |",
                  f"| always E | {fE[test].mean()*100:.1f} | - | 100% |",
                  f"| logistic regression (threshold {best_t:.3f}) | {routed[test].mean()*100:.1f} | "
                  f"{fmt(paired_bootstrap_test(list(routed[test]), list(fE[test])))} | {(prob[test] >= best_t).mean()*100:.0f}% |",
                  f"| single threshold: E if {sf} {'>=' if ss > 0 else '<='} {st:.3f} | {routed1[test].mean()*100:.1f} | "
                  f"{fmt(paired_bootstrap_test(list(routed1[test]), list(fE[test])))} | "
                  f"{((ss * (col[test] - st)) >= 0).mean()*100:.0f}% |",
                  f"| oracle P / E | {o2[test].mean()*100:.1f} | {fmt(paired_bootstrap_test(list(o2[test]), list(fE[test])))} | - |",
                  "", "Logistic regression coefficients (standardised features, positive = E more likely better): "
                  + ", ".join(f"{f} {c:+.2f}" for f, c in coef) + f". Accuracy of the E-better label on held-out "
                  f"questions with d != 0: {((prob >= 0.5) == y)[test & (d != 0)].mean()*100:.0f}%.", ""]
    lines += ["## Conclusions", "",
              "* **The graph facts help when passage retrieval misses the answer and a fact still comes from the "
              "gold section.** On these 342 questions E gains 4.6 points over passages (B alone does as well there). "
              "Over all retrieval misses the gain is 1.3 points; over the hits it is 0.1.",
              "* **They hurt when the passages are already right and the facts are off-topic.** When the gold section "
              "is in the top 5 but no fact comes from it (1,005 questions), E loses 1.0 point: the extra facts "
              "distract from a good context.",
              "* **Gains are small and spread out by question type.** E is ahead on follow-up turns (+0.6), on "
              "'yes' replies of the user (+1.0), when the question names a linked entity (+0.9) and in the VA "
              "domain (+0.9); it gives nothing on first turns and in StudentAid. Per question, E is better on 48% "
              "and worse on 42%, so the average gain of 0.5 is the net of many changes in both directions.",
              "* **A router is not worth it with these signals.** The oracle between P and E gains 3.3 points, but "
              "picking the better of two runs of the same system already gains 2.9, so almost all of the oracle "
              "gain is run-to-run variation. A logistic regression on features available before generation "
              "predicts the better system only 52% of the time and is 0.5 points worse than always using E; the "
              "best single threshold (top reranker score) is 0.2 points worse. The useful signal (whether a fact "
              "comes from the gold section) needs the gold answer and is not available at run time.",
              "* **Graph facts only (B) are clearly worse overall** (24.1), but close to E where passage retrieval "
              "misses and a gold fact exists (26.2 vs 25.2); the three-way oracle gain (+5.8) is mostly noise too.",
              ""]
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    json.dump([{k: (bool(v) if isinstance(v, np.bool_) else v) for k, v in r.items()} for r in rows],
              open(OUT / "per_question.json", "w"), default=float)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
