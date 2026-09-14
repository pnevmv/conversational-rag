"""Entity resolution for extracted KG mentions.

Pipeline:
  1. Type conflicts: mentions sharing a normalised name but extracted with different
     types get the majority type over all mentions (ties: ENTITY_TYPES order).
  2. Blocking by type. Service, Requirement, Role and Outcome are compared only within
     the same domain; Organization, Document, ContactPoint, Amount and TimeLimit also
     across domains.
  3. Mentions with the same normalised name in a block form one name group (merged).
  4. Candidate pairs of name groups:
       - rules, merged automatically: alias (an alias or parenthetical abbreviation of
         one group is a name of the other), acronym (initials of a multi-word name equal
         the other name, e.g. Department of Motor Vehicles / DMV), form number (two
         Documents citing the same form code, e.g. IRP-6 / IRP6);
       - embedding cosine of the names (bge-small-en-v1.5) plus graph signals, as in
         ch. 6.1.4 of the book: +SAME_DOC_BONUS if both occur in the same document,
         +SHARED_NEIGHBOUR_BONUS per shared relation neighbour (capped).
  5. Three bands on the resulting score: >= UPPER merge, < LOWER never merge, in
     between an LLM confirms (temperature 0, strict JSON, cached). Only each name
     group's TOP_K nearest neighbours enter the LLM band, so the number of LLM calls
     grows linearly with the corpus rather than quadratically.
  6. Constrained clustering: accepted pairs are merged (rules first, then by score)
     unless the two clusters contain a cannot-link pair, i.e. a pair the LLM rejected or
     two Amount / TimeLimit / ContactPoint groups with different values. This stops
     chains such as A=B, B=C merging A and C when the LLM said A != C.

Commands:
    python -m src.kg.resolve calibrate   # LLM-judge pairs over a score range, per-bin agreement
    python -m src.kg.resolve run         # resolve the pilot, export clusters for review
"""
import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import numpy as np

from src.kg.extract import ExtractionCache, _call_llm
from src.kg.extract_closed import loadable_relations
from src.kg.pilot2_stats import normalized_key
from src.kg.schema import ENTITY_TYPES
from src.llm.client import LLMClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_DIR = PROJECT_ROOT / "experiments" / "kg"
DEFAULT_INPUT = KG_DIR / "pilot3_closed_extraction.jsonl"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "experiments" / "cache" / "kg_er"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

CROSS_DOMAIN_TYPES = {"Organization", "Document", "ContactPoint", "Amount", "TimeLimit"}

# Score bands, chosen from the pilot calibration (experiments/kg/er_calibration.json):
# below 0.75 the LLM judged 1 of 100 sampled pairs the same entity; above it the rate never
# exceeds ~57%, even at score >= 0.95 (contrastive siblings such as Subsidized / Unsubsidized
# loans embed almost identically). So no score is safe to auto-merge: the upper band is
# disabled and only the alias, acronym and form-number rules merge without the LLM.
UPPER = 1.01
LOWER = 0.75
TOP_K = 5
SAME_DOC_BONUS = 0.02
SHARED_NEIGHBOUR_BONUS = 0.03
MAX_NEIGHBOUR_BONUS = 0.06

# Calibration: every pair scoring >= CAL_MIN, plus a random sample just below it.
CAL_MIN = 0.75
CAL_LOW_RANGE = (0.65, 0.75)
CAL_LOW_SAMPLE = 100

_ACRONYM_STOP = {"of", "and", "the", "for", "on", "in", "to", "a", "an", "&"}
# An alias counts as merge evidence only if it looks like an abbreviation (MAGI, VR&E, IRB):
# the model sometimes fills `alias` with a category label ("Sales Tax Form").
_ABBREVIATION = re.compile(r"^[A-Z][A-Za-z0-9&./\-]{1,9}$")
VALUE_TYPES = {"Amount", "TimeLimit", "ContactPoint"}
_PAREN = re.compile(r"\(([^)]+)\)")
_FORM_CODES = [
    re.compile(r"\b([A-Z]{1,5})[ -]?(\d{1,4}[A-Z]?)\b"),        # IRP-6, MV-232, DTF-803, DD214
    re.compile(r"\b(\d{2}[A-Z]?)-(\d{2,5}[a-z]?)\b"),           # VA Form 21-22a, 21P-509
]

JUDGE_PROMPT = """Two entity mentions were extracted from U.S. government-service web pages ({domain_note}).
Decide whether they refer to the SAME real-world entity (the same service, organisation, document,
requirement, amount, time limit, role, outcome or contact point), not merely related or similar ones.
A general concept and a specific variant of it are NOT the same (e.g. "home loan" vs "VA direct home loan").

Entity A ({type_a}):
{desc_a}

Entity B ({type_b}):
{desc_b}
"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"same": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["same", "reason"],
    "additionalProperties": False,
}


# --- mentions ---------------------------------------------------------------------------

def key_of(name: str) -> str:
    return normalized_key(name) or name.casefold().strip()


def load_mentions(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    """One mention per extracted entity per section, with its relation neighbours."""
    mentions: List[Dict[str, Any]] = []
    for path in paths:
        for r in map(json.loads, open(path, encoding="utf-8")):
            if r["status"] == "skipped" or r["status"].startswith("error"):
                continue
            neighbours: Dict[str, Set[str]] = defaultdict(set)
            for rel in loadable_relations(r):
                neighbours[rel["source"].casefold()].add(key_of(rel["target"]))
                neighbours[rel["target"].casefold()].add(key_of(rel["source"]))
            for i, e in enumerate(r["entities"]):
                mentions.append({
                    "mention_id": f"{r['section_id']}#{i}",
                    "section_id": r["section_id"], "doc_id": r["doc_id"], "domain": r["domain"],
                    "title": r["title"], "name": e["name"], "alias": e.get("alias"), "value": e.get("value"),
                    "extracted_type": e["type"], "type": e["type"], "evidence": e["evidence"],
                    "neighbours": sorted(neighbours[e["name"].casefold()]),
                })
    return mentions


def resolve_types(mentions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Majority vote of the type over mentions sharing a normalised name; returns the conflicts."""
    order = {t: i for i, t in enumerate(ENTITY_TYPES)}
    by_key: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in mentions:
        by_key[key_of(m["name"])].append(m)
    conflicts = []
    for key, ms in by_key.items():
        votes = Counter(m["extracted_type"] for m in ms)
        if len(votes) < 2:
            continue
        winner = sorted(votes.items(), key=lambda kv: (-kv[1], order[kv[0]]))[0][0]
        for m in ms:
            m["type"] = winner
        conflicts.append({"name": key, "votes": dict(votes), "resolved_type": winner})
    return conflicts


def block_of(m: Dict[str, Any]) -> str:
    return m["type"] if m["type"] in CROSS_DOMAIN_TYPES else f"{m['type']}|{m['domain']}"


# --- name groups ------------------------------------------------------------------------

def build_groups(mentions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for m in mentions:
        gid = f"{block_of(m)}::{key_of(m['name'])}"
        g = groups.setdefault(gid, {
            "gid": gid, "block": block_of(m), "type": m["type"], "key": key_of(m["name"]),
            "names": Counter(), "aliases": set(), "mention_ids": [], "sections": set(), "docs": set(),
            "domains": set(), "titles": set(), "neighbours": set(), "evidence": [], "values": set(),
        })
        g["names"][m["name"]] += 1
        for alias in [m["alias"]] + _PAREN.findall(m["name"]):
            if alias and _ABBREVIATION.match(alias.strip()):
                g["aliases"].add(key_of(alias))
        if m["value"] and m["type"] in VALUE_TYPES:
            g["values"].add(re.sub(r"[^a-z0-9]", "", m["value"].casefold()))
        g["mention_ids"].append(m["mention_id"])
        g["sections"].add(m["section_id"])
        g["docs"].add(m["doc_id"])
        g["domains"].add(m["domain"])
        g["titles"].add(m["title"])
        g["neighbours"].update(m["neighbours"])
        if len(g["evidence"]) < 2:
            g["evidence"].append(m["evidence"])
    owners: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for g in groups.values():
        for alias in g["aliases"]:
            owners[(g["block"], alias)].add(g["gid"])
    for g in groups.values():
        g["aliases"] = {a for a in g["aliases"] if len(owners[(g["block"], a)]) == 1}
    return groups


def value_conflict(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Two value-typed groups whose stated values are disjoint cannot be the same entity."""
    return a["type"] in VALUE_TYPES and bool(a["values"]) and bool(b["values"]) and not (a["values"] & b["values"])


def _acronym(key: str) -> Optional[str]:
    words = [w for w in key.split() if w not in _ACRONYM_STOP]
    return "".join(w[0] for w in words) if len(words) >= 2 else None


def _form_codes(group: Dict[str, Any]) -> Set[str]:
    codes = set()
    for name in group["names"]:
        for pattern in _FORM_CODES:
            for a, b in pattern.findall(name):
                codes.add(re.sub(r"[^A-Za-z0-9]", "", f"{a}{b}").upper())
    return codes


def rule_match(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[str]:
    if a["aliases"] & ({b["key"]} | b["aliases"]) or b["aliases"] & ({a["key"]} | a["aliases"]):
        return "alias"
    for x, y in ((a, b), (b, a)):
        acr = _acronym(x["key"])
        if acr and len(acr) >= 2 and acr == y["key"].replace(" ", ""):
            return "acronym"
    if a["type"] == b["type"] == "Document" and _form_codes(a) & _form_codes(b):
        return "form_number"
    return None


def graph_bonus(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    bonus = SAME_DOC_BONUS if a["docs"] & b["docs"] else 0.0
    shared = len((a["neighbours"] - {a["key"], b["key"]}) & (b["neighbours"] - {a["key"], b["key"]}))
    return bonus + min(MAX_NEIGHBOUR_BONUS, SHARED_NEIGHBOUR_BONUS * shared)


def candidate_pairs(groups: Dict[str, Dict[str, Any]], min_score: float,
                    top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    """Within-block pairs that match a rule, or score >= min_score (and, if top_k is set,
    are among the top_k highest-scoring partners of at least one of the two groups)."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL)
    by_block: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for g in groups.values():
        by_block[g["block"]].append(g)

    pairs = []
    for block, gs in sorted(by_block.items()):
        if len(gs) < 2:
            continue
        gs.sort(key=lambda g: g["gid"])
        emb = model.encode([g["names"].most_common(1)[0][0] for g in gs], normalize_embeddings=True)
        sims = emb @ emb.T
        scored = {}
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                a, b = gs[i], gs[j]
                rule = rule_match(a, b)
                cos = float(sims[i, j])
                score = min(1.0, cos + graph_bonus(a, b))
                if rule or score >= min_score:
                    scored[(i, j)] = {"block": block, "a": a["gid"], "b": b["gid"], "cosine": round(cos, 4),
                                      "bonus": round(score - cos, 4), "score": round(score, 4), "rule": rule}
        if top_k is not None:
            keep = {k for k, p in scored.items() if p["rule"]}
            partners: Dict[int, List[Tuple[float, Tuple[int, int]]]] = defaultdict(list)
            for (i, j), p in scored.items():
                partners[i].append((p["score"], (i, j)))
                partners[j].append((p["score"], (i, j)))
            for lst in partners.values():
                keep.update(k for _, k in sorted(lst, reverse=True)[:top_k])
            scored = {k: v for k, v in scored.items() if k in keep}
        pairs.extend(scored.values())
    return pairs


# --- LLM confirmation -------------------------------------------------------------------

def _describe(g: Dict[str, Any]) -> str:
    names = [n for n, _ in g["names"].most_common(4)]
    lines = [f"- name: {names[0]}"]
    if len(names) > 1:
        lines.append(f"- also written as: {'; '.join(names[1:])}")
    if g["aliases"]:
        lines.append(f"- abbreviations: {'; '.join(sorted(g['aliases']))}")
    lines.append(f"- pages: {'; '.join(sorted(g['titles'])[:2])}")
    lines.extend(f"- evidence: \"{ev}\"" for ev in g["evidence"])
    return "\n".join(lines)


def judge(pair: Dict[str, Any], groups: Dict[str, Dict[str, Any]], client: LLMClient,
          cache: ExtractionCache) -> Dict[str, Any]:
    a, b = groups[pair["a"]], groups[pair["b"]]
    domains = sorted(a["domains"] | b["domains"])
    prompt = JUDGE_PROMPT.format(domain_note=f"domain: {', '.join(domains)}", type_a=a["type"],
                                 type_b=b["type"], desc_a=_describe(a), desc_b=_describe(b))
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    key = f"{pair['a']}||{pair['b']}"
    raw = cache.get(key, prompt_hash)
    if raw is None:
        raw = _call_llm(client, prompt, 5, schema=JUDGE_SCHEMA, schema_name="kg_entity_match")
        cache.put(key, prompt_hash, raw)
    return json.loads(raw)


def judge_all(pairs: List[Dict[str, Any]], groups: Dict[str, Dict[str, Any]], workers: int = 8) -> None:
    from concurrent.futures import ThreadPoolExecutor

    client, cache = LLMClient(), ExtractionCache(DEFAULT_CACHE_DIR)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda p: judge(p, groups, client, cache), pairs))
    for p, res in zip(pairs, results):
        p["llm_same"], p["llm_reason"] = res["same"], res["reason"]


# --- clustering -------------------------------------------------------------------------

def decide(pair: Dict[str, Any], upper: float, lower: float) -> str:
    if pair["rule"]:
        return "auto_rule"
    if pair.get("value_conflict"):
        return "reject_value"
    if pair["score"] >= upper:
        return "auto_score"
    if pair["score"] < lower:
        return "reject"
    return "llm"


def cluster(groups: Dict[str, Dict[str, Any]], accepted: List[Dict[str, Any]],
            cannot_link: Set[frozenset]) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Merge accepted pairs (rules first, then by score) unless a cannot-link pair would
    end up inside one cluster. Returns ({gid: root}, pairs skipped because of a conflict)."""
    root = {gid: gid for gid in groups}
    members = {gid: {gid} for gid in groups}
    blocked = []
    for p in sorted(accepted, key=lambda p: (p["rule"] is None, -p["score"])):
        ra, rb = root[p["a"]], root[p["b"]]
        if ra == rb:
            continue
        if any(frozenset((x, y)) in cannot_link for x in members[ra] for y in members[rb]):
            blocked.append(p)
            continue
        keep, drop = min(ra, rb), max(ra, rb)
        for gid in members[drop]:
            root[gid] = keep
        members[keep] |= members.pop(drop)
    return root, blocked


def canonical_name(gs: List[Dict[str, Any]]) -> str:
    names: Counter = Counter()
    for g in gs:
        names.update(g["names"])
    return sorted(names.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[0][0]


# --- commands ---------------------------------------------------------------------------

def _prepare(paths: List[Path]):
    mentions = load_mentions(paths)
    conflicts = resolve_types(mentions)
    groups = build_groups(mentions)
    return mentions, conflicts, groups


def calibrate(paths: List[Path], workers: int) -> None:
    _, _, groups = _prepare(paths)
    pairs = [p for p in candidate_pairs(groups, CAL_LOW_RANGE[0]) if not p["rule"]]
    high = [p for p in pairs if p["score"] >= CAL_MIN]
    low = [p for p in pairs if CAL_LOW_RANGE[0] <= p["score"] < CAL_LOW_RANGE[1]]
    low = random.Random(42).sample(low, min(CAL_LOW_SAMPLE, len(low)))
    judged = high + low
    judge_all(judged, groups, workers)

    edges = [0.65, 0.70, 0.75, 0.80, 0.85, 0.88, 0.90, 0.93, 0.95, 1.01]
    bins = []
    for lo, hi in zip(edges, edges[1:]):
        ps = [p for p in judged if lo <= p["score"] < hi]
        bins.append({"score_from": lo, "score_to": min(hi, 1.0), "pairs": len(ps),
                     "llm_same": sum(p["llm_same"] for p in ps),
                     "llm_same_rate": round(sum(p["llm_same"] for p in ps) / len(ps), 3) if ps else None})
    out = {"pairs_judged": len(judged), "pairs_scoring_at_least_cal_min": len(high),
           "low_range_sample": len(low), "bins": bins}
    (KG_DIR / "er_calibration.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    with open(KG_DIR / "er_calibration_pairs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["block", "name_a", "name_b", "cosine", "bonus", "score", "llm_same", "llm_reason"])
        for p in sorted(judged, key=lambda p: -p["score"]):
            w.writerow([p["block"], groups[p["a"]]["names"].most_common(1)[0][0],
                        groups[p["b"]]["names"].most_common(1)[0][0], p["cosine"], p["bonus"], p["score"],
                        p["llm_same"], p["llm_reason"]])
    print(f"Judged {len(judged)} pairs ({len(high)} with score >= {CAL_MIN}, {len(low)} sampled below)")
    for b in bins:
        print(f"  [{b['score_from']:.2f}, {b['score_to']:.2f})  pairs={b['pairs']:4}  same={b['llm_same']:4}  "
              f"rate={b['llm_same_rate']}")


def run(paths: List[Path], workers: int, upper: float, lower: float, top_k: Optional[int]) -> None:
    mentions, conflicts, groups = _prepare(paths)
    pairs = candidate_pairs(groups, lower, top_k)
    for p in pairs:
        p["value_conflict"] = value_conflict(groups[p["a"]], groups[p["b"]])
        p["band"] = decide(p, upper, lower)
    middle = [p for p in pairs if p["band"] == "llm"]
    judge_all(middle, groups, workers)
    accepted = [p for p in pairs if p["band"] in ("auto_rule", "auto_score") or p.get("llm_same")]
    cannot_link = {frozenset((p["a"], p["b"])) for p in pairs
                   if p["band"] == "reject_value" or (p["band"] == "llm" and not p["llm_same"])}
    root, blocked = cluster(groups, accepted, cannot_link)
    for p in blocked:
        p["blocked"] = True

    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for gid, r in root.items():
        members[r].append(groups[gid])
    rules_of: Dict[str, List[str]] = defaultdict(list)
    for p in accepted:
        if p.get("blocked"):
            continue
        rules_of[root[p["a"]]].append(p["rule"] or ("llm" if p["band"] == "llm" else f"score {p['score']:.2f}"))

    clusters = []
    for r, gs in members.items():
        surface = sorted({n for g in gs for n in g["names"]}, key=str.casefold)
        clusters.append({
            "root": r, "type": gs[0]["type"], "block": gs[0]["block"], "canonical_name": canonical_name(gs),
            "n_name_groups": len(gs), "n_mentions": sum(len(g["mention_ids"]) for g in gs),
            "n_sections": len(set().union(*(g["sections"] for g in gs))),
            "n_documents": len(set().union(*(g["docs"] for g in gs))),
            "domains": sorted(set().union(*(g["domains"] for g in gs))),
            "surface_names": surface, "merge_evidence": Counter(rules_of[r]),
            "mention_ids": [mid for g in gs for mid in g["mention_ids"]],
        })
    clusters.sort(key=lambda c: (c["type"], c["canonical_name"].casefold()))
    for i, c in enumerate(clusters, start=1):
        c["entity_id"] = f"E{i:05d}"

    # Mention -> resolved entity, for loading the KG layer later.
    entity_of = {mid: c["entity_id"] for c in clusters for mid in c["mention_ids"]}
    with open(KG_DIR / "er_pilot_mentions.jsonl", "w", encoding="utf-8") as f:
        for m in mentions:
            f.write(json.dumps({"mention_id": m["mention_id"], "section_id": m["section_id"], "name": m["name"],
                                "extracted_type": m["extracted_type"], "type": m["type"],
                                "entity_id": entity_of[m["mention_id"]]}, ensure_ascii=False) + "\n")

    # Hand-check sheet: clusters that merge differently written names.
    review = [c for c in clusters if len({n.casefold() for n in c["surface_names"]}) > 1]
    with open(KG_DIR / "er_pilot_clusters.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entity_id", "type", "domains", "canonical_name", "surface_names", "n_mentions",
                    "n_sections", "n_documents", "merge_evidence", "label", "note"])
        for c in review:
            w.writerow([c["entity_id"], c["type"], " ".join(c["domains"]), c["canonical_name"],
                        " | ".join(c["surface_names"]), c["n_mentions"], c["n_sections"], c["n_documents"],
                        "; ".join(f"{k} x{v}" for k, v in c["merge_evidence"].items()), "", ""])
    with open(KG_DIR / "er_pilot_pairs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["block", "name_a", "name_b", "cosine", "bonus", "score", "rule", "band", "llm_same",
                    "llm_reason", "merged"])
        for p in sorted(pairs, key=lambda p: -p["score"]):
            w.writerow([p["block"], groups[p["a"]]["names"].most_common(1)[0][0],
                        groups[p["b"]]["names"].most_common(1)[0][0], p["cosine"], p["bonus"], p["score"],
                        p["rule"] or "", p["band"], p.get("llm_same", ""), p.get("llm_reason", ""),
                        p in accepted and not p.get("blocked")])

    bands = Counter(p["band"] for p in pairs)
    summary = {
        "thresholds": {"upper": upper, "lower": lower, "top_k": top_k, "same_doc_bonus": SAME_DOC_BONUS,
                       "shared_neighbour_bonus": SHARED_NEIGHBOUR_BONUS, "max_neighbour_bonus": MAX_NEIGHBOUR_BONUS},
        "mentions": len(mentions), "name_groups": len(groups), "entities": len(clusters),
        "type_conflicts": conflicts,
        "candidate_pairs": len(pairs), "bands": dict(bands),
        "rules": dict(Counter(p["rule"] for p in pairs if p["rule"])),
        "llm_confirmed": sum(1 for p in middle if p["llm_same"]), "llm_rejected": sum(1 for p in middle if not p["llm_same"]),
        "merged_pairs": len(accepted) - len(blocked),
        "blocked_by_cannot_link": len(blocked),
        "clusters_for_review": len(review),
        "largest_clusters": [{"canonical_name": c["canonical_name"], "type": c["type"],
                              "n_name_groups": c["n_name_groups"], "n_mentions": c["n_mentions"]}
                             for c in sorted(clusters, key=lambda c: -c["n_name_groups"])[:10]],
    }
    (KG_DIR / "er_pilot_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                   encoding="utf-8")
    print(f"{len(mentions)} mentions -> {len(groups)} name groups -> {len(clusters)} entities")
    print(f"type conflicts resolved: {len(conflicts)}; candidate pairs: {len(pairs)} {dict(bands)}")
    print(f"LLM confirmed {summary['llm_confirmed']}, rejected {summary['llm_rejected']}; "
          f"blocked by cannot-link: {len(blocked)}; clusters to review: {len(review)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["calibrate", "run"])
    parser.add_argument("--input", type=Path, nargs="+", default=[DEFAULT_INPUT])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--upper", type=float, default=UPPER)
    parser.add_argument("--lower", type=float, default=LOWER)
    parser.add_argument("--top-k", type=int, default=TOP_K, help="0 = all pairs above the lower threshold")
    args = parser.parse_args()
    if args.command == "calibrate":
        calibrate(args.input, args.workers)
    else:
        run(args.input, args.workers, args.upper, args.lower, args.top_k or None)


if __name__ == "__main__":
    main()
