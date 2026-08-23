import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_qa_pairs
from src.llm import LLMClient

DEFAULT_PROMPT_TEMPLATE = (
    "Answer the following question as accurately as possible.\n\n"
    "Question:\n{question}"
)


def format_prompt(question: str, template: str = DEFAULT_PROMPT_TEMPLATE) -> str:
    """Format the question into the strict LLM-only baseline prompt."""
    return template.format(question=question)


def run_llm_baseline(
    split: str = "validation",
    domain: str = None,
    max_examples: int = 50,
    output_path: Path = None,
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE,
) -> Dict[str, Any]:
    """
    Execute the LLM-only baseline evaluation over MultiDoc2Dial examples.

    Args:
        split: Dataset split ('validation' or 'train').
        domain: Optional domain filter ('dmv', 'ssa', 'va', 'studentaid').
        max_examples: Number of deterministic examples to evaluate.
        output_path: Path to output JSONL file.
        prompt_template: Formatting string containing {question}.

    Returns:
        Summary statistics dictionary.
    """
    output_file = output_path or (
        PROJECT_ROOT / "experiments" / "results" / "llm_baseline.jsonl"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading MultiDoc2Dial...")
    print(f"Using {split} split")
    if domain:
        print(f"Filtering domain: {domain}")

    examples: List[Dict[str, Any]] = load_qa_pairs(
        split=split,
        domain=domain,
        max_examples=max_examples,
    )

    total_selected = len(examples)
    print(f"Selected {total_selected} examples\n")

    if total_selected == 0:
        print("No examples found matching criteria.")
        return {"total": 0, "successful": 0, "failed": 0}

    print("Initializing LLM client...")
    client = LLMClient()
    print(f"Model: {client.default_model}\n")

    print("Running LLM-only baseline...\n")

    successful = 0
    failed = 0

    # Open file in append/write mode
    with open(output_file, "w", encoding="utf-8") as f:
        for idx, ex in enumerate(examples, start=1):
            ex_id = ex["example_id"]
            question = ex["question"]
            prompt = format_prompt(question, prompt_template)

            print(f"[{idx}/{total_selected}] (ID: {ex_id})")
            print(f"  Q: {question[:80]}{'...' if len(question) > 80 else ''}")

            start_time = time.time()
            try:
                # LLM receives strictly the question prompt (no context, no retrieval)
                model_answer = client.generate(prompt=prompt)
                status = "success"
                error_msg = None
                successful += 1
                elapsed = time.time() - start_time
                print(f"  ✓ Answered in {elapsed:.2f}s")
            except Exception as e:
                model_answer = None
                status = "error"
                error_msg = str(e)
                failed += 1
                elapsed = time.time() - start_time
                print(f"  ✗ Failed after {elapsed:.2f}s: {error_msg}")

            record = {
                "example_id": ex_id,
                "domain": ex["domain"],
                "dialogue_id": ex["dialogue_id"],
                "turn_id": ex["turn_id"],
                "question": question,
                "reference_answer": ex["reference_answer"],
                "document_id": ex["document_id"],
                "grounding": ex["grounding"],
                "prompt": prompt,
                "model_answer": model_answer,
                "status": status,
                "error": error_msg,
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    print("\n----------------------------------------")
    print(f"Completed: {total_selected}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"\nResults saved to:")
    print(f"{output_file}")
    print("----------------------------------------\n")

    return {
        "total": total_selected,
        "successful": successful,
        "failed": failed,
        "output_file": str(output_file),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run LLM-only baseline on MultiDoc2Dial."
    )
    parser.add_argument(
        "--split",
        type=str,
        default="validation",
        choices=["validation", "train"],
        help="Dataset split to evaluate on (default: validation)",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Optional domain filter (e.g. dmv, ssa, va, studentaid)",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=50,
        help="Number of deterministic examples to run (default: 50)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom path to save the output JSONL file",
    )

    args = parser.parse_args()

    custom_output = Path(args.output) if args.output else None

    run_llm_baseline(
        split=args.split,
        domain=args.domain,
        max_examples=args.max_examples,
        output_path=custom_output,
    )


if __name__ == "__main__":
    main()
