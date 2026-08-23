import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_qa_pairs
from src.llm import LLMClient
from src.rag import HybridRetriever

TOP_K = 5

PROMPT_TEMPLATE = (
    "You are a helpful assistant. Answer the question using only the context provided below.\n"
    "If the context does not contain enough information, say so briefly.\n\n"
    "Context:\n{context}\n\n"
    "Question:\n{question}"
)


def format_context(results: List[Dict[str, Any]]) -> str:
    parts = []
    for r in results:
        header = f"[{r['rank']}] {r['title']}"
        if r.get("section_title"):
            header += f" — {r['section_title']}"
        parts.append(f"{header}\n{r['text']}")
    return "\n\n".join(parts)


def recall_at_k(retrieved: List[Dict], grounding: List[Dict], k: int) -> float:
    if not grounding:
        return 0.0
    gold = {(g["doc_id"], str(g["id_sp"])) for g in grounding if "doc_id" in g and "id_sp" in g}
    if not gold:
        return 0.0
    retrieved_set = {(r["doc_id"], str(r["id_sp"])) for r in retrieved[:k]}
    return len(gold & retrieved_set) / len(gold)


def run_rag_hybrid_baseline(
    split: str = "validation",
    domain: Optional[str] = None,
    max_examples: int = 50,
    top_k: int = TOP_K,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    output_file = output_path or (
        PROJECT_ROOT / "experiments" / "results" / "rag_hybrid_baseline.jsonl"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Loading MultiDoc2Dial...")
    examples: List[Dict[str, Any]] = load_qa_pairs(
        split=split, domain=domain, max_examples=max_examples
    )
    total = len(examples)
    print(f"Selected {total} examples\n")

    print("Building hybrid index (BM25 + dense bge-small)...")
    retriever = HybridRetriever()
    retriever.build_index()
    print(f"Corpus: {retriever.corpus_size:,} spans\n")

    print("Initializing LLM client...")
    client = LLMClient()
    print(f"Model: {client.default_model}\n")

    print(f"Running hybrid RAG baseline (BM25 + bge-small, RRF, top_k={top_k})...\n")

    successful = 0
    failed = 0
    recall_1_sum = 0.0
    recall_5_sum = 0.0

    with open(output_file, "w", encoding="utf-8") as f:
        for idx, ex in enumerate(examples, start=1):
            ex_id = ex["example_id"]
            question = ex["question"]
            grounding = ex.get("grounding", [])

            print(f"[{idx}/{total}] (ID: {ex_id})")
            print(f"  Q: {question[:80]}{'...' if len(question) > 80 else ''}")

            retrieved = retriever.retrieve(question, top_k=top_k)
            r1 = recall_at_k(retrieved, grounding, k=1)
            r5 = recall_at_k(retrieved, grounding, k=5)
            recall_1_sum += r1
            recall_5_sum += r5
            print(f"  Retrieved {len(retrieved)} spans  |  Recall@1={r1:.2f}  Recall@5={r5:.2f}")

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
                "document_id": ex["document_id"],
                "grounding": grounding,
                "retrieved_spans": retrieved,
                "context": context,
                "prompt": prompt,
                "model_answer": model_answer,
                "recall_at_1": r1,
                "recall_at_5": r5,
                "status": status,
                "error": error_msg,
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    n_eval = successful + failed
    avg_r1 = recall_1_sum / n_eval if n_eval else 0.0
    avg_r5 = recall_5_sum / n_eval if n_eval else 0.0

    print("\n----------------------------------------")
    print(f"Completed : {total}")
    print(f"Successful: {successful}")
    print(f"Failed    : {failed}")
    print(f"\nRetrieval (avg over all examples):")
    print(f"  Recall@1: {avg_r1:.4f}  ({avg_r1*100:.2f}%)")
    print(f"  Recall@5: {avg_r5:.4f}  ({avg_r5*100:.2f}%)")
    print(f"\nResults saved to:\n  {output_file}")
    print("----------------------------------------\n")

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "avg_recall_at_1": avg_r1,
        "avg_recall_at_5": avg_r5,
        "output_file": str(output_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Run hybrid RAG baseline on MultiDoc2Dial.")
    parser.add_argument("--split", default="validation", choices=["validation", "train"])
    parser.add_argument("--domain", default=None)
    parser.add_argument("--max-examples", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    run_rag_hybrid_baseline(
        split=args.split,
        domain=args.domain,
        max_examples=args.max_examples,
        top_k=args.top_k,
        output_path=Path(args.output) if args.output else None,
    )


if __name__ == "__main__":
    main()
