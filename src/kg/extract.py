"""Pilot open extraction of entities and relations from MultiDoc2Dial sections.

Samples a fixed set of sections (per-domain, fixed seed), asks the LLM for
open-typed entities and relations with verbatim evidence quotes (temperature 0,
strict JSON schema), and saves the raw outputs as JSONL. Nothing is written to
Neo4j at this stage: these are raw mentions for schema design.

Usage:
    python -m src.kg.extract
    python -m src.kg.extract --per-domain 8 --seed 42 --workers 8
"""
import argparse
import hashlib
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAIError

from src.data.loader import load_doc_domain_map, load_sections
from src.llm.client import LLMClient
from src.llm.parallel import _is_retriable

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments" / "kg" / "pilot_open_extraction.jsonl"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "experiments" / "cache" / "kg_extract"

DOMAINS = ["dmv", "ssa", "studentaid", "va"]
# Skip heading-only or near-empty sections: they carry nothing to extract.
MIN_SPANS = 2
MIN_CHARS = 150

EXTRACTION_PROMPT = """You are building a knowledge graph of U.S. government services from official web pages.

Extract the entities and relations stated in the section below.

Entities: the concrete things a citizen would ask about, e.g. services, benefits, programs, agencies, offices, forms and documents, requirements and eligibility conditions, fees and amounts, deadlines and time periods, people or roles, and outcomes or consequences. Choose each entity's type freely, as a short CamelCase noun (e.g. "Benefit", "Form", "EligibilityCondition").

Relations: directed links between two extracted entities, with a short UPPER_SNAKE_CASE relation name (e.g. "REQUIRES", "ISSUED_BY"). "source" and "target" must be exactly the "name" of an extracted entity.

Rules:
- Extract only what the section states; do not add background knowledge.
- "evidence" must be a short quote (at most ~25 words) copied verbatim from the section text that supports the entity or relation.
- Use a canonical, specific name for each entity (e.g. "Supplemental Security Income (SSI)", not "it" or "this benefit").
- If the section states nothing extractable, return empty lists.

Domain: {domain}
Document title: {title}
Section heading: {heading}
Section text:
\"\"\"
{text}
\"\"\"
"""

EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "type", "evidence"],
                "additionalProperties": False,
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "relation": {"type": "string"},
                    "target": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["source", "relation", "target", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["entities", "relations"],
    "additionalProperties": False,
}


def sample_sections(per_domain: int, seed: int) -> List[Dict[str, Any]]:
    """Pick `per_domain` content-bearing sections from each domain, deterministically."""
    domain_map = load_doc_domain_map()
    by_domain: Dict[str, List[Dict[str, Any]]] = {d: [] for d in DOMAINS}
    for s in load_sections():
        if len(s["span_ids"]) >= MIN_SPANS and len(s["text"]) >= MIN_CHARS:
            by_domain[domain_map[s["doc_id"]]].append({**s, "domain": domain_map[s["doc_id"]]})

    rng = random.Random(seed)
    picked: List[Dict[str, Any]] = []
    for dom in DOMAINS:
        pool = sorted(by_domain[dom], key=lambda s: s["section_id"])
        picked.extend(rng.sample(pool, per_domain))
    return picked


def build_prompt(section: Dict[str, Any]) -> str:
    return EXTRACTION_PROMPT.format(
        domain=section["domain"],
        title=section["title"],
        heading=section["section_title"] or "(none)",
        text=section["text"],
    )


class ExtractionCache:
    """One JSON file per (section_id, prompt hash) under cache_dir."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, section_id: str, prompt_hash: str) -> Path:
        key = hashlib.sha256(f"{section_id}\x00{prompt_hash}".encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def get(self, section_id: str, prompt_hash: str) -> Optional[str]:
        p = self._path(section_id, prompt_hash)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))["response"]
        return None

    def put(self, section_id: str, prompt_hash: str, response: str) -> None:
        self._path(section_id, prompt_hash).write_text(
            json.dumps({"section_id": section_id, "prompt_hash": prompt_hash, "response": response},
                       ensure_ascii=False),
            encoding="utf-8",
        )


def _call_llm(
    client: LLMClient,
    prompt: str,
    max_retries: int,
    schema: Optional[Dict[str, Any]] = None,
    schema_name: str = "kg_extraction",
) -> str:
    """Call the model at temperature 0 with a strict JSON schema (open schema by default)."""
    for attempt in range(max_retries):
        try:
            response = client.client.responses.create(
                model=client.default_model,
                input=prompt,
                temperature=0,
                text={"format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema or EXTRACTION_SCHEMA,
                    "strict": True,
                }},
            )
            return response.output_text
        except OpenAIError as exc:
            if _is_retriable(exc) and attempt < max_retries - 1:
                time.sleep(min(2 ** attempt, 60))
            else:
                raise RuntimeError(f"LLM API request failed: {exc}") from None
    raise RuntimeError("LLM API request failed after retries")


def extract_section(
    client: LLMClient, cache: ExtractionCache, section: Dict[str, Any], max_retries: int = 5
) -> Tuple[Dict[str, Any], str]:
    """Return (parsed extraction, status) for one section."""
    prompt = build_prompt(section)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    raw = cache.get(section["section_id"], prompt_hash)
    status = "cached"
    if raw is None:
        raw = _call_llm(client, prompt, max_retries)
        cache.put(section["section_id"], prompt_hash, raw)
        status = "success"
    return {"prompt_hash": prompt_hash, **json.loads(raw)}, status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-domain", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    sections = sample_sections(args.per_domain, args.seed)
    print(f"Sampled {len(sections)} sections ({args.per_domain}/domain, seed={args.seed})")

    client = LLMClient()
    cache = ExtractionCache(args.cache_dir)

    def _task(section: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "section_id": section["section_id"],
            "domain": section["domain"],
            "doc_id": section["doc_id"],
            "title": section["title"],
            "heading": section["section_title"],
            "text": section["text"],
            "model": client.default_model,
        }
        try:
            extraction, status = extract_section(client, cache, section)
            record.update(extraction)
            record["status"] = status
        except Exception as exc:
            record.update({"entities": [], "relations": [], "status": f"error: {exc}"})
        return record

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(_task, sections))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    statuses: Dict[str, int] = {}
    for r in records:
        key = r["status"] if not r["status"].startswith("error") else "error"
        statuses[key] = statuses.get(key, 0) + 1
    n_ent = sum(len(r["entities"]) for r in records)
    n_rel = sum(len(r["relations"]) for r in records)
    print(f"Statuses: {statuses}")
    print(f"Extracted {n_ent} entities, {n_rel} relations -> {args.output}")


if __name__ == "__main__":
    main()
