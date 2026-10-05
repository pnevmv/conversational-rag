"""Entity-linking evaluation on dev-500 (phase 1).

Link recall@k: share of examples where one of the top-k entities is mentioned in a gold
section. Compares query variants and linker settings.

    python -m src.kg_rag.eval_linking
"""
import json
import math
import random
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src.kg_rag.linker import EntityLinker
from src.kg_rag.queries import DOMAIN_CONFIDENCE, OUT_DIR, load_step4

KS = (1, 5, 10)
CHANCE_SEEDS = 5
VARIANTS = ("raw", "rewritten", "rewritten_agent")


def wilson(n: int, total: int, z: float = 1.96) -> Tuple[Optional[float], Optional[float]]:
    if total == 0:
        return None, None
    p = n / total
    den = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return centre - half, centre + half


def query_text(rec: Dict[str, Any], variant: str) -> str:
    if variant == "raw":
        return rec["raw"]
    if variant == "rewritten":
        return rec["rewritten"]
    return rec["rewritten"] + (f"\n{rec['last_agent']}" if rec["last_agent"] else "")


def hits(linked: List[Dict[str, Any]], gold: set, linker: EntityLinker) -> Dict[int, bool]:
    first = next((i for i, l in enumerate(linked[:max(KS)])
                  if gold & set(linker.by_id[l["entity_id"]]["section_ids"])), None)
    return {k: first is not None and first < k for k in KS}


def summarise(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    def block(sub):
        out = {"n": len(sub)}
        for k in KS:
            n = sum(r[key][str(k)] for r in sub)
            lo, hi = wilson(n, len(sub))
            out[f"R@{k}"] = {"hits": n, "recall": n / len(sub) if sub else None, "ci": [lo, hi]}
        return out
    res = {"all": block(rows), "by_domain": {}, "doc_switch": block([r for r in rows if r["is_doc_switch"]]),
           "same_doc": block([r for r in rows if not r["is_doc_switch"]]),
           "unanswerable": block([r for r in rows if r["is_unanswerable"]])}
    for dom in sorted({r["domain"] for r in rows}):
        res["by_domain"][dom] = block([r for r in rows if r["domain"] == dom])
    return res


def main() -> None:
    step4 = load_step4()
    records = step4["records"]
    linker = EntityLinker("full")
    examples = [ex for ex in step4["examples"] if records[ex["example_id"]]["gold_sections"]]
    print(f"{len(examples)} of {len(step4['examples'])} dev-500 examples have a gold section; "
          f"hub cap degree > {linker.hub_cap:g} ({sum(linker.is_hub(e) for e in linker.entities)} hubs)")

    configs = {f"{v}": dict(variant=v) for v in VARIANTS}
    configs.update({
        "rewritten_dense_only": dict(variant="rewritten", method="dense"),
        "rewritten_bm25_only": dict(variant="rewritten", method="bm25"),
        "rewritten_no_domain_filter": dict(variant="rewritten", domain_filter="none"),
        "rewritten_no_hub_skip": dict(variant="rewritten", skip_hubs=False),
        "rewritten_gold_domain": dict(variant="rewritten", domain_filter="gold"),
        "raw+rewritten": dict(variant=("raw", "rewritten")),
        "raw+rewritten_no_hub_skip": dict(variant=("raw", "rewritten"), skip_hubs=False),
    })

    texts = {v: [query_text(records[ex["example_id"]], v) for ex in examples] for v in VARIANTS}
    t = time.time()
    embs = {v: linker.encode(texts[v]) for v in VARIANTS}
    encode_ms = (time.time() - t) / (len(VARIANTS) * len(examples)) * 1000

    rows: List[Dict[str, Any]] = []
    for i, ex in enumerate(examples):
        rec = records[ex["example_id"]]
        rows.append({"example_id": ex["example_id"], "domain": ex["domain"],
                     "is_doc_switch": ex.get("is_doc_switch", False),
                     "is_unanswerable": ex.get("is_unanswerable", False), "gold_sections": rec["gold_sections"],
                     "pred_domain": rec["pred_domain"], "pred_domain_conf": rec["pred_domain_conf"],
                     "queries": {v: texts[v][i] for v in VARIANTS}, "linked": {}, "hit": {}})

    # Ceiling: the gold section has any entity / any non-hub entity.
    sec_entities: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in linker.entities:
        for sid in e["section_ids"]:
            sec_entities[sid].append(e)
    for r in rows:
        ents = [e for sid in r["gold_sections"] for e in sec_entities.get(sid, [])]
        r["gold_has_entity"] = bool(ents)
        r["gold_has_nonhub_entity"] = any(not linker.is_hub(e) for e in ents)

    link_ms, fanout, chance = {}, {}, {}
    for name, cfg in configs.items():
        v = cfg["variant"]
        t = time.time()
        for i, r in enumerate(rows):
            mode = cfg.get("domain_filter", "pred")
            dom = (r["pred_domain"] if mode == "pred" and r["pred_domain_conf"] >= DOMAIN_CONFIDENCE
                   else r["domain"] if mode == "gold" else None)
            opts = dict(domain=dom, skip_hubs=cfg.get("skip_hubs", True), method=cfg.get("method", "rrf"))
            if isinstance(v, tuple):
                linked = linker.link_many([r["queries"][x] for x in v], [embs[x][i] for x in v], k=max(KS), **opts)
            else:
                linked = linker.link(r["queries"][v], k=max(KS), query_emb=embs[v][i], **opts)
            r["linked"][name] = [{"entity_id": l["entity_id"], "name": l["name"], "type": l["type"]} for l in linked]
            r["hit"][name] = {str(k): h for k, h in hits(linked, set(r["gold_sections"]), linker).items()}
        link_ms[name] = (time.time() - t) / len(rows) * 1000
        for r in rows:
            r[f"hit_{name}"] = r["hit"][name]
        # Fan-out: distinct sections the top-k entities are mentioned in (a hit through an
        # entity mentioned in hundreds of sections is cheap).
        fanout[name] = {}
        for k in KS:
            vals = sorted(len({sid for l in r["linked"][name][:k] for sid in linker.by_id[l["entity_id"]]["section_ids"]})
                          for r in rows)
            fanout[name][f"top{k}"] = {"median": vals[len(vals) // 2], "mean": sum(vals) / len(vals)}
        # Chance level: give every example the linked entities of another example of the same
        # domain (random permutation within domain, averaged over seeds).
        chance[name] = {}
        for k in KS:
            total = 0
            for seed in range(CHANCE_SEEDS):
                rng = random.Random(seed)
                for dom in sorted({r["domain"] for r in rows}):
                    sub = [r for r in rows if r["domain"] == dom]
                    donors = sub[:]
                    rng.shuffle(donors)
                    for r, d in zip(sub, donors):
                        total += hits(d["linked"][name], set(r["gold_sections"]), linker)[k]
            chance[name][f"R@{k}"] = total / (CHANCE_SEEDS * len(rows))

    n_conf = sum(r["pred_domain_conf"] >= DOMAIN_CONFIDENCE for r in rows)
    summary = {
        "examples": len(rows), "dev500": len(step4["examples"]),
        "hub_cap_degree": linker.hub_cap, "hubs": sum(linker.is_hub(e) for e in linker.entities),
        "domain_prediction": {
            "accuracy": sum(r["pred_domain"] == r["domain"] for r in rows) / len(rows),
            "confident": n_conf, "threshold": DOMAIN_CONFIDENCE,
            "accuracy_when_confident": sum(r["pred_domain"] == r["domain"] for r in rows
                                           if r["pred_domain_conf"] >= DOMAIN_CONFIDENCE) / max(n_conf, 1),
        },
        "ceiling": {"gold_has_entity": sum(r["gold_has_entity"] for r in rows) / len(rows),
                    "gold_has_nonhub_entity": sum(r["gold_has_nonhub_entity"] for r in rows) / len(rows)},
        "latency_ms": {"encode_per_query": encode_ms, **{f"link_{k}": v for k, v in link_ms.items()}},
        "rewrite": step4["rewrite_stats"],
        "configs": {name: {**summarise(rows, f"hit_{name}"), "fanout_sections": fanout[name],
                           "chance": chance[name]} for name in configs},
    }
    (OUT_DIR / "phase1_linking.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with open(OUT_DIR / "phase1_linking.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if not k.startswith("hit_")}, ensure_ascii=False) + "\n")

    print(f"domain prediction: {summary['domain_prediction']}")
    print(f"ceiling: {summary['ceiling']}")
    for name, s in summary["configs"].items():
        a = s["all"]
        print(f"{name:28} " + "  ".join(f"R@{k} {a[f'R@{k}']['recall']:.1%}" for k in KS)
              + f"   switch R@10 {s['doc_switch']['R@10']['recall']:.1%} (n={s['doc_switch']['n']})"
              + f"   chance R@10 {chance[name]['R@10']:.1%}   fan-out@10 median {fanout[name]['top10']['median']}"
              + f"   {link_ms[name]:.0f} ms")


if __name__ == "__main__":
    main()
