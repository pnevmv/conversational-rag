"""Oracle-context baseline: LLM receives gold grounding sections as context.

The only difference from the RAG pipelines is the context source — gold
sections are looked up directly from the dataset rather than retrieved.
Everything else (prompt template, question, dialogue history structure,
output schema) is identical to the RAG experiments.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_qa_pairs, load_sections
from src.llm import LLMClient

UNANSWERABLE = "Unfortunately, no relevant information is found."
TOP_K = 5

PROMPT_TEMPLATE = (
    "You are a government services agent. Answer the customer's question in 1-2 plain sentences "
    "using only the context below. No bullet points, no bold text, no preamble.\n"
    "If the context does not contain relevant information, reply exactly: "
    "\"Unfortunately, no relevant information is found.\"\n\n"
    "Examples:\n"
    "Customer: Do I need insurance to register my vehicle?\n"
    "Agent: Yes, you must have liability insurance to register a vehicle in New York.\n\n"
    "Customer: How do I pay DIAL-IN search account fees?\n"
    "Agent: Paying customers must include a deposit with the application; "
    "your first deposit must cover two months of searches.\n\n"
    "Context:\n{context}\n\n"
    "Customer: {question}\n"
    "Agent:"
)


def build_span_index(sections: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    """Map every (doc_id, span_id_str) to the section that contains it."""
    index: Dict[tuple, Dict[str, Any]] = {}
    for sec in sections:
        for sid in sec["span_ids"]:
            key = (sec["doc_id"], str(sid))
            if key not in index:
                index[key] = sec
    return index


def gold_sections_for(
    grounding: List[Dict[str, Any]],
    span_index: Dict[tuple, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return deduplicated sections that cover all gold grounding spans."""
    seen: set = set()
    result: List[Dict[str, Any]] = []
    for g in grounding:
        if "doc_id" not in g or "id_sp" not in g:
            continue
        key = (g["doc_id"], str(g["id_sp"]))
        sec = span_index.get(key)
        if sec is None:
            continue
        sec_key = (sec["doc_id"], sec["id_sp"])
        if sec_key not in seen:
            seen.add(sec_key)
            result.append(sec)
    return result


def format_context(sections: List[Dict[str, Any]]) -> str:
    parts = []
    for rank, sec in enumerate(sections, start=1):
        header = f"[{rank}] {sec['title']}"
        if sec.get("section_title"):
            header += f" — {sec['section_title']}"
        parts.append(f"{header}\n{sec['text']}")
    return "\n\n".join(parts)


def run_oracle_context(
    split: str = "validation",
    domain: Optional[str] = None,
    max_examples: int = 50,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    output_file = output_path or (
        PROJECT_ROOT / "experiments" / "results" / "oracle_context.jsonl"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Loading MultiDoc2Dial...")
    examples: List[Dict[str, Any]] = load_qa_pairs(
        split=split, domain=domain, max_examples=max_examples
    )
    total = len(examples)
    print(f"Selected {total} examples\n")

    print("Building section span index...")
    sections = load_sections()
    span_index = build_span_index(sections)
    print(f"Indexed {len(span_index):,} (doc_id, span_id) pairs from {len(sections):,} sections\n")

    print("Initializing LLM client...")
    client = LLMClient()
    print(f"Model: {client.default_model}\n")

    print("Running oracle-context baseline...\n")

    successful = 0
    failed = 0
    no_gold_sections = 0

    with open(output_file, "w", encoding="utf-8") as f:
        for idx, ex in enumerate(examples, start=1):
            ex_id = ex["example_id"]
            question = ex["question"]
            grounding = ex.get("grounding", [])
            is_unans = ex.get("is_unanswerable", False)

            print(f"[{idx}/{total}] [{ex['domain']}] (ID: {ex_id})")
            print(f"  Q: {question[:80]}{'...' if len(question) > 80 else ''}")

            gold_secs = gold_sections_for(grounding, span_index)
            if not gold_secs:
                no_gold_sections += 1
                if is_unans:
                    print("  (unanswerable — empty context)")
                else:
                    print("  WARNING: answerable but no gold section found")

            context = format_context(gold_secs)
            prompt = PROMPT_TEMPLATE.format(context=context, question=question)

            start = time.time()
            try:
                model_answer = client.generate(prompt=prompt)
                status = "success"
                error_msg = None
                successful += 1
                print(f"  Answered in {time.time() - start:.2f}s")
            except Exception as e:
                model_answer = None
                status = "error"
                error_msg = str(e)
                failed += 1
                print(f"  Failed: {error_msg}")

            # recall is always 1.0 for answerable (gold sections provided),
            # None for unanswerable (no gold grounding exists)
            recall = 1.0 if (not is_unans and gold_secs) else None

            record = {
                "example_id": ex_id,
                "domain": ex["domain"],
                "dialogue_id": ex["dialogue_id"],
                "turn_id": ex["turn_id"],
                "question": question,
                "reference_answer": ex["reference_answer"],
                "is_unanswerable": is_unans,
                "is_doc_switch": ex.get("is_doc_switch", False),
                "document_id": ex["document_id"],
                "grounding": grounding,
                "gold_sections": [
                    {"doc_id": s["doc_id"], "id_sp": s["id_sp"],
                     "title": s["title"], "section_title": s["section_title"]}
                    for s in gold_secs
                ],
                "context": context,
                "prompt": prompt,
                "model_answer": model_answer,
                "recall_at_1": recall,
                "recall_at_5": recall,
                "domain_recall": None,
                "status": status,
                "error": error_msg,
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    print("\n----------------------------------------")
    print(f"Completed          : {total}")
    print(f"Successful         : {successful}")
    print(f"Failed             : {failed}")
    print(f"No gold section    : {no_gold_sections}")
    print(f"\nResults saved to:\n  {output_file}")
    print("----------------------------------------\n")

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "no_gold_sections": no_gold_sections,
        "output_file": str(output_file),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Oracle-context baseline: LLM with gold grounding sections."
    )
    parser.add_argument("--split", default="validation", choices=["validation", "train"])
    parser.add_argument("--domain", default=None)
    parser.add_argument("--max-examples", type=int, default=50,
                        help="0 = full split")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    run_oracle_context(
        split=args.split,
        domain=args.domain,
        max_examples=args.max_examples if args.max_examples > 0 else None,
        output_path=Path(args.output) if args.output else None,
    )


if __name__ == "__main__":
    main()
