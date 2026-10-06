"""Run the main systems on a whole split (full validation or test) with cached LLM calls.

Order: the Step 4 retrieval (rewrites, hybrid top-50, reranker; cached in
experiments/kg_rag/step4_<split>.json), then the Step 4 pipelines, then the KG pipelines.
Results go to experiments/results/<split>/ in the same format as dev-500.

    python experiments/run_split.py --split validation --workers 12
    python experiments/run_split.py --split test --systems llm_baseline rag_rewrite_rerank_v2 ...

Progress is printed with timestamps, so a run in the background can be followed with
`tail -f` on its log.
"""
import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.run_dev_subset import (RERANKER_CACHE_DIR, _build_agent_prompt, _load_few_shot_examples,
                                        run_llm_baseline, run_oracle_context, run_rag_retrieval, write_jsonl)
from src.data.loader import load_doc_domain_map
from src.kg_rag import run_qa
from src.kg_rag.queries import load_step4, split_examples
from src.llm import LLMCache, LLMClient

CACHE_DIR = PROJECT_ROOT / "experiments" / "cache"
STEP4_SYSTEMS = ["llm_baseline", "oracle_context_v2", "rag_rewrite_baseline_v2", "rag_rewrite_rerank",
                 "rag_rewrite_rerank_v2"]
KG_SYSTEMS = ["kg_sections", "kg_facts", "step4_plus_facts", "step4_plus_random_facts"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--systems", nargs="+", choices=STEP4_SYSTEMS + KG_SYSTEMS)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if args.split == "test" and not args.systems:
        parser.error("on the test split, list the frozen systems explicitly with --systems")
    systems = args.systems or STEP4_SYSTEMS + KG_SYSTEMS
    out_dir = run_qa.results_dir(args.split)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    examples = split_examples(args.split)
    log(f"{args.split}: {len(examples)} examples; systems: {', '.join(systems)}")

    log("Step 4 retrieval (rewrites, hybrid top-50, reranker)")
    load_step4(args.split, workers=args.workers)
    log("Step 4 retrieval done")

    client, cache = LLMClient(), LLMCache(CACHE_DIR)
    agent_prompt = _build_agent_prompt(_load_few_shot_examples())
    ddm = load_doc_domain_map()
    step4 = [s for s in systems if s in STEP4_SYSTEMS]
    if any(s.startswith("rag_") for s in step4):
        from src.rag import HybridRetriever, QueryRewriter, Reranker
        retriever = HybridRetriever()
        retriever.build_index()
        rewriter = QueryRewriter(client=client)
        reranker = Reranker(cache_dir=RERANKER_CACHE_DIR)
    for name in step4:
        log(f"=== {name} ===")
        if name == "llm_baseline":
            records = run_llm_baseline(examples, client, cache, args.workers)
        elif name == "oracle_context_v2":
            records = run_oracle_context(examples, client, cache, args.workers, prompt_template=agent_prompt)
        else:
            records = run_rag_retrieval(
                examples, retriever, client, cache, ddm, args.workers, rewriter=rewriter,
                reranker=reranker if "rerank" in name else None,
                prompt_template=None if name == "rag_rewrite_rerank" else agent_prompt)
        write_jsonl(records, out_dir / f"{name}.jsonl")
        log(f"{name} done ({sum(1 for r in records if r['status'] == 'error')} errors)")

    kg = [s for s in systems if s in KG_SYSTEMS]
    if kg:
        log(f"=== KG pipelines: {', '.join(kg)} ===")
        run_qa.run(args.split, kg, args.workers)
    log(f"all done in {(time.time() - t0) / 60:.0f} min; cache {cache.stats}; results in {out_dir}")


if __name__ == "__main__":
    main()
