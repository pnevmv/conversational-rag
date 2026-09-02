import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_qa_pairs, load_doc_domain_map
from src.llm import LLMClient
from src.rag import DenseRetriever

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


def format_context(results: List[Dict[str, Any]]) -> str:
    parts = []
    for r in results:
        header = f"[{r['rank']}] {r['title']}"
        if r.get("section_title"):
            header += f" — {r['section_title']}"
        parts.append(f"{header}\n{r['text']}")
    return "\n\n".join(parts)


def recall_at_k(
    retrieved: List[Dict[str, Any]],
    grounding: List[Dict[str, Any]],
    k: int,
) -> float:
    if not grounding:
        return 0.0
    gold = {(g["doc_id"], str(g["id_sp"])) for g in grounding if "doc_id" in g and "id_sp" in g}
    if not gold:
        return 0.0
    retrieved_set: set = set()
    for r in retrieved[:k]:
        for sp_id in r.get("span_ids", [str(r["id_sp"])]):
            retrieved_set.add((r["doc_id"], str(sp_id)))
    return len(gold & retrieved_set) / len(gold)


def domain_recall_at_k(retrieved, gold_domain, k, doc_domain_map):
    top = retrieved[:k]
    if not top:
        return 0.0
    hits = sum(1 for r in top if doc_domain_map.get(r["doc_id"]) == gold_domain)
    return hits / len(top)


def run_rag_dense_baseline(
    split: str = "validation",
    domain: Optional[str] = None,
    max_examples: int = 50,
    top_k: int = TOP_K,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    output_file = output_path or (
        PROJECT_ROOT / "experiments" / "results" / "rag_dense_baseline.jsonl"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Loading MultiDoc2Dial...")
    examples: List[Dict[str, Any]] = load_qa_pairs(
        split=split, domain=domain, max_examples=max_examples
    )
    total = len(examples)
    print(f"Selected {total} examples\n")

    retriever = DenseRetriever()
    _ = retriever.corpus_size
    print(f"Corpus: {retriever.corpus_size:,} sections\n")

    doc_domain_map = load_doc_domain_map()

    print("Initializing LLM client...")
    client = LLMClient()
    print(f"Model: {client.default_model}\n")

    print(f"Running dense RAG baseline (top_k={top_k})...\n")

    successful = 0
    failed = 0
    recall_1_sum = 0.0
    recall_5_sum = 0.0
    domain_recall_sum = 0.0

    with open(output_file, "w", encoding="utf-8") as f:
        for idx, ex in enumerate(examples, start=1):
            ex_id = ex["example_id"]
            question = ex["question"]
            grounding = ex.get("grounding", [])

            print(f"[{idx}/{total}] [{ex['domain']}] (ID: {ex_id})")
            print(f"  Q: {question[:80]}{'...' if len(question) > 80 else ''}")

            retrieved = retriever.retrieve(question, top_k=top_k)
            r1 = recall_at_k(retrieved, grounding, k=1)
            r5 = recall_at_k(retrieved, grounding, k=5)
            dr = domain_recall_at_k(retrieved, ex["domain"], top_k, doc_domain_map)
            recall_1_sum += r1
            recall_5_sum += r5
            domain_recall_sum += dr
            print(f"  Recall@1={r1:.2f}  Recall@5={r5:.2f}  DomainRecall={dr:.2f}")

            context = format_context(retrieved)
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

            record = {
                "example_id": ex_id,
                "domain": ex["domain"],
                "dialogue_id": ex["dialogue_id"],
                "turn_id": ex["turn_id"],
                "question": question,
                "reference_answer": ex["reference_answer"],
                "is_unanswerable": ex.get("is_unanswerable", False),
                "document_id": ex["document_id"],
                "grounding": grounding,
                "retrieved_spans": retrieved,
                "context": context,
                "prompt": prompt,
                "model_answer": model_answer,
                "recall_at_1": r1,
                "recall_at_5": r5,
                "domain_recall": dr,
                "status": status,
                "error": error_msg,
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    n_eval = successful + failed
    avg_r1 = recall_1_sum / n_eval if n_eval else 0.0
    avg_r5 = recall_5_sum / n_eval if n_eval else 0.0
    avg_dr = domain_recall_sum / n_eval if n_eval else 0.0

    print("\n----------------------------------------")
    print(f"Completed : {total}")
    print(f"Successful: {successful}")
    print(f"Failed    : {failed}")
    print(f"\nRetrieval (avg over all examples):")
    print(f"  Recall@1:      {avg_r1:.4f}  ({avg_r1*100:.2f}%)")
    print(f"  Recall@5:      {avg_r5:.4f}  ({avg_r5*100:.2f}%)")
    print(f"  Domain Recall: {avg_dr:.4f}  ({avg_dr*100:.2f}%)")
    print(f"\nResults saved to:\n  {output_file}")
    print("----------------------------------------\n")

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "avg_recall_at_1": avg_r1,
        "avg_recall_at_5": avg_r5,
        "avg_domain_recall": avg_dr,
        "output_file": str(output_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Run dense RAG baseline on MultiDoc2Dial.")
    parser.add_argument("--split", default="validation", choices=["validation", "train"])
    parser.add_argument("--domain", default=None)
    parser.add_argument("--max-examples", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    run_rag_dense_baseline(
        split=args.split,
        domain=args.domain,
        max_examples=args.max_examples,
        top_k=args.top_k,
        output_path=Path(args.output) if args.output else None,
    )


if __name__ == "__main__":
    main()
