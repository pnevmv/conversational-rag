"""Annotation set for extraction precision, entities and relations separately, on documents not used before.

No LLM calls: everything is read from the existing full graph (the exports in experiments/kg_rag/,
the extraction in experiments/kg/full_v21_extraction.jsonl and the entity resolution in
experiments/kg/er_full_mentions.jsonl).

    python experiments/kg_eval/build_annotation_set.py

Documents: 6, a seeded random sample stratified by domain (one per domain, then the rest from all
remaining documents). Every document that appears in an earlier KG file (pilots, v2 re-extraction,
annotation and control samples, regression set) is excluded, and so is every document that shares a
page title (the part before '#') or the text of a section with one of them, since identical sections
are extracted once and shared. Writes to experiments/kg_eval/:
docs.json, entities.csv, relations.csv and, for a file with more than 150 rows, a seeded sample
of 150 rows (*_sample150.csv) to label instead.
"""
import csv
import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG = PROJECT_ROOT / "experiments" / "kg"
EXPORTS = PROJECT_ROOT / "experiments" / "kg_rag"
OUT = PROJECT_ROOT / "experiments" / "kg_eval"
SEED = 42
N_DOCS = 6
MAX_ROWS = 150
MAX_CONTEXT = 300
# Files of the full build (not earlier annotation work) are not checked for used documents.
FULL_BUILD_PREFIXES = ("full_", "er_full", "kg_stats_full", "kg_coverage_full", "er_calibration", "er_annotation")
LABEL_COLUMNS = ["correct", "error_type", "note"]


def load_jsonl(path: Path) -> List[Dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def used_documents(all_docs: Set[str]) -> Dict[str, List[str]]:
    """Documents named in any earlier KG file (pilots, v2, annotation, control, regression)."""
    used: Dict[str, List[str]] = defaultdict(list)
    for root, _, files in os.walk(KG):
        for name in sorted(files):
            if name.startswith(FULL_BUILD_PREFIXES):
                continue
            path = Path(root) / name
            text = path.read_text(encoding="utf-8", errors="ignore")
            for d in all_docs:
                if d + "::" in text or f'"{d}"' in text:
                    used[d].append(str(path.relative_to(KG)))
    return used


def related_documents(sections: Dict[str, Dict], used: Set[str]) -> Set[str]:
    """Documents with the same page title as a used document, or with a section text identical to one."""
    base = lambda d: d.split("#")[0].strip()
    used_titles = {base(d) for d in used}
    norm = lambda t: " ".join(t.split())
    used_texts = {norm(r["text"]) for r in sections.values() if r["doc_id"] in used}
    return {r["doc_id"] for r in sections.values()
            if r["doc_id"] not in used and (base(r["doc_id"]) in used_titles or norm(r["text"]) in used_texts)}


def choose_documents(domain_of: Dict[str, str], excluded: Set[str]) -> List[str]:
    rng = random.Random(SEED)
    pool = sorted(d for d in domain_of if d not in excluded)
    chosen = []
    for dom in sorted(set(domain_of.values())):
        chosen.append(rng.choice([d for d in pool if domain_of[d] == dom]))
    rest = [d for d in pool if d not in chosen]
    chosen += rng.sample(rest, N_DOCS - len(chosen))
    return chosen


def span_no(section_id: str) -> int:
    m = re.search(r"::(\d+)$", section_id)
    return int(m.group(1)) if m else 0


def short(text: str, n: int = MAX_CONTEXT) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 3].rsplit(" ", 1)[0] + " ..."


def sentence_with(text: str, name: str) -> str:
    """The sentence of the section text that shares the most words with the mention name."""
    words = set(re.findall(r"\w+", name.lower()))
    best, score = "", -1
    for s in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
        sc = len(words & set(re.findall(r"\w+", s.lower())))
        if sc > score:
            best, score = s, sc
    return best


def section_title(sec: Dict) -> str:
    return sec["heading"].strip() or "(intro of the page)"


def write_csv(path: Path, rows: List[Dict], columns: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def sample(rows: List[Dict]) -> List[Dict]:
    idx = sorted(random.Random(SEED).sample(range(len(rows)), MAX_ROWS))
    return [rows[i] for i in idx]


def main() -> None:
    sections = {r["section_id"]: r for r in load_jsonl(KG / "full_v21_extraction.jsonl")}
    domain_of = {r["doc_id"]: r["domain"] for r in sections.values()}
    title_of = {r["doc_id"]: r["title"] for r in sections.values()}
    used = used_documents(set(domain_of))
    related = related_documents(sections, set(used))
    docs = choose_documents(domain_of, set(used) | related)
    doc_rank = {d: k for k, d in enumerate(docs)}
    in_docs = lambda sid: sid.split("::")[0] in doc_rank
    order = lambda sid: (doc_rank[sid.split("::")[0]], span_no(sid))

    entities = {e["entity_id"]: e for e in json.load(open(EXPORTS / "entities_full.json", encoding="utf-8"))}
    relations = json.load(open(EXPORTS / "relations_full.json", encoding="utf-8"))

    # ---------------------------------------------------------------- entities
    # First mention of each entity in the chosen documents, in document and section order.
    first: Dict[str, Dict] = {}
    for m in load_jsonl(KG / "er_full_mentions.jsonl"):
        if not in_docs(m["section_id"]):
            continue
        eid = "full:" + m["entity_id"] if not m["entity_id"].startswith("full:") else m["entity_id"]
        if eid not in entities:
            continue
        if eid not in first or order(m["section_id"]) < order(first[eid]["section_id"]):
            first[eid] = m
    ent_rows = []
    for eid, m in sorted(first.items(), key=lambda kv: (order(kv[1]["section_id"]), kv[0])):
        e, sec = entities[eid], sections[m["section_id"]]
        extracted = next((x for x in sec["entities"] if x.get("name") == m["name"] and x.get("text")), None)
        context = extracted["text"] if extracted else sentence_with(sec["text"], m["name"])
        ent_rows.append({"entity_id": eid, "name": e["name"], "type": e["type"],
                         "aliases": " | ".join(e["forms"]), "doc_id": sec["doc_id"],
                         "section_title": section_title(sec), "context": short(context)})

    # ---------------------------------------------------------------- relations
    rel_rows = []
    for r in relations:
        quotes = [q for q in r["evidence"] if in_docs(q["section_id"])]
        sids = [s for s in r["section_ids"] if in_docs(s)]
        if not quotes and not sids:
            continue
        sid = min([q["section_id"] for q in quotes] or sids, key=order)
        h, t = entities[r["source"]], entities[r["target"]]
        rel_rows.append({"rel_id": f"{r['source']}|{r['relation']}|{r['target']}",
                         "head": f"{h['name']} ({h['type']})", "relation": r["relation"],
                         "tail": f"{t['name']} ({t['type']})",
                         "evidence": " || ".join(q["text"] for q in sorted(quotes, key=lambda q: order(q["section_id"])))
                                     or "(no quote stored)",
                         "doc_id": sid.split("::")[0], "section_title": section_title(sections[sid]), "_order": order(sid)})
    rel_rows.sort(key=lambda r: (r["_order"], r["rel_id"]))

    # ---------------------------------------------------------------- write
    OUT.mkdir(parents=True, exist_ok=True)
    ent_cols = ["entity_id", "name", "type", "aliases", "doc_id", "section_title", "context"] + LABEL_COLUMNS
    rel_cols = ["rel_id", "head", "relation", "tail", "evidence", "doc_id", "section_title"] + LABEL_COLUMNS
    write_csv(OUT / "entities.csv", ent_rows, ent_cols)
    write_csv(OUT / "relations.csv", rel_rows, rel_cols)
    info = {"seed": SEED, "excluded_used": len(used), "excluded_related": len(related),
            "documents": [{"doc_id": d, "domain": domain_of[d], "title": title_of[d],
                           "sections": sum(1 for s in sections if s.split("::")[0] == d),
                           "entities": sum(1 for r in ent_rows if r["doc_id"] == d),
                           "relations": sum(1 for r in rel_rows if r["doc_id"] == d)} for d in docs],
            "entities": len(ent_rows), "relations": len(rel_rows), "samples": {}}
    for name, rows, cols in (("entities", ent_rows, ent_cols), ("relations", rel_rows, rel_cols)):
        if len(rows) > MAX_ROWS:
            write_csv(OUT / f"{name}_sample150.csv", sample(rows), cols)
            info["samples"][name] = f"{name}_sample150.csv"
        else:
            (OUT / f"{name}_sample150.csv").unlink(missing_ok=True)
    (OUT / "docs.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"excluded {len(used)} documents used before and {len(related)} sharing a title or a section with them; "
          f"{len(domain_of) - len(used) - len(related)} remain")
    for d in info["documents"]:
        print(f"  [{d['domain']}] {d['doc_id']}  ({d['sections']} sections, {d['entities']} entities, {d['relations']} relations)")
    print(f"entities.csv {len(ent_rows)} rows, relations.csv {len(rel_rows)} rows")
    for name, f in info["samples"].items():
        print(f"  {name}: more than {MAX_ROWS} rows, label {f} (seeded sample of {MAX_ROWS})")


if __name__ == "__main__":
    sys.exit(main())
