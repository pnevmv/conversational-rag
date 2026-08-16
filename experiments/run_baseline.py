import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import LLMClient
from src.evaluation import ExperimentLogger


def run_baseline_sample():
    """Run single sample through naive LLM baseline and record to JSONL."""
    client = LLMClient()
    logger = ExperimentLogger(experiment_name="llm_baseline")

    question = "What documents do I need to apply for a driver's license?"
    print(f"Running baseline on: {question}\n")

    answer = client.generate(prompt=question)
    print("Answer:")
    print(answer)

    entry = logger.log(
        question=question,
        answer=answer,
        model=client.default_model,
        dataset="multidoc2dial_sample",
    )
    print(f"\nResult logged to: {logger.log_file}")
    return entry


if __name__ == "__main__":
    run_baseline_sample()
