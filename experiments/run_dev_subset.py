"""Run all pipelines on the fixed 500-example dev subset using parallel LLM calls.

Pipelines executed:
  llm_baseline, oracle_context, rag_bm25, rag_dense, rag_hybrid, rag_hybrid_rewrite,
  oracle_v2, rewrite_v2,            (agent-style prompt v2)
  rewrite_rerank, rewrite_rerank_v2 (cross-encoder reranker, old/new prompt)

Results written to experiments/results/dev_500/<pipeline>.jsonl (same schema as
the full-split JSONL files so evaluate_diagnostics.py works unchanged).

LLM calls use a thread pool (--workers, default 8) and a disk cache
(experiments/cache/) so re-runs skip already-answered prompts.
Reranker scores are cached separately in experiments/cache/reranker/.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_qa_pairs, load_sections, load_doc_domain_map
from src.evaluation.metrics import compute_metrics
from src.llm import LLMClient, LLMCache, generate_batch
from src.rag import BM25Retriever, DenseRetriever, HybridRetriever, QueryRewriter, Reranker
from src.rag.reranker import MAX_TOKENS as RERANKER_MODEL_MAX_TOKENS

RESULTS_DIR = PROJECT_ROOT / "experiments" / "results" / "dev_500"
CACHE_DIR = PROJECT_ROOT / "experiments" / "cache"
RERANKER_CACHE_DIR = PROJECT_ROOT / "experiments" / "cache" / "reranker"
DEV_IDS_FILE = PROJECT_ROOT / "data" / "dev_500_ids.json"
TOP_K = 5
RERANKER_RETRIEVE_K = 50

RAG_PROMPT = (
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
    "Context:\n{context}\n\nCustomer: {question}\nAgent:"
)

LLM_PROMPT = (
    "You are a government services agent. Answer the customer's question in 1-2 plain sentences. "
    "No bullet points, no bold text, no preamble. "
    "If you don't know, reply exactly: \"Unfortunately, no relevant information is found.\"\n\n"
    "Customer: {question}\nAgent:"
)


def _load_few_shot_examples() -> List[Tuple[str, str]]:
    """Return 3 (question, answer) pairs from the train split (seed=42, 3 domains)."""
    from collections import defaultdict

    train = load_qa_pairs(split="train", max_examples=None)
    by_domain: Dict[str, List] = defaultdict(list)
    for ex in train:
        by_domain[ex["domain"]].append(ex)

    def _is_good(ex: Dict) -> bool:
        ref = ex["reference_answer"]
        if ex.get("is_unanswerable"):
            return False
        if ref.endswith("?"):
            return False
        if len(ref) < 30 or len(ref) > 220:
            return False
        words = ref.lower().split()
        return any(w in words[:3] for w in ["you", "your", "you'll", "you're", "you've"])

    picks: List[Tuple[str, str]] = []
    for domain in ["dmv", "ssa", "va"]:
        pool = [ex for ex in by_domain[domain] if _is_good(ex)]
        rng = random.Random(42)
        rng.shuffle(pool)
        if pool:
            ex = pool[0]
            picks.append((ex["question"], ex["reference_answer"]))
    return picks


def _build_agent_prompt(few_shots: List[Tuple[str, str]]) -> str:
    """Build the agent-style (v2) prompt template with embedded few-shot examples."""
    ex_str = "\n\n".join(f"Customer: {q}\nAgent: {a}" for q, a in few_shots)
    return (
        "You are a government services agent. Answer the customer's question in 1–2 short, "
        "plain sentences using only the context below. Address the customer directly using "
        "second person (you/your). Do not use bullet points, bold text, or numbered lists. "
        "Do not begin your reply with phrases like \"Based on the context\" or "
        "\"According to the document\".\n"
        "If the context does not contain the answer, reply exactly: "
        "\"Unfortunately, no relevant information is found.\"\n\n"
        f"Examples:\n{ex_str}\n\n"
        "Context:\n{context}\n\nCustomer: {question}\nAgent:"
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def load_dev_examples() -> List[Dict[str, Any]]:
    ids = json.loads(DEV_IDS_FILE.read_text(encoding="utf-8"))
    id_set = set(ids)
    all_examples = load_qa_pairs(split="validation", max_examples=None)
    by_id = {ex["example_id"]: ex for ex in all_examples}
    ordered = [by_id[eid] for eid in ids if eid in by_id]
    missing = id_set - {ex["example_id"] for ex in ordered}
    if missing:
        print(f"  WARNING: {len(missing)} dev IDs not found in dataset")
    return ordered


def format_context(retrieved: List[Dict[str, Any]]) -> str:
    parts = []
    for r in retrieved:
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
    rs: set = set()
    for r in retrieved[:k]:
        for sp in r.get("span_ids", [str(r["id_sp"])]):
            rs.add((r["doc_id"], str(sp)))
    return len(gold & rs) / len(gold)


def domain_recall_at_k(retrieved: List[Dict], gold_domain: str, k: int, ddm: Dict) -> float:
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for r in top if ddm.get(r["doc_id"]) == gold_domain) / len(top)


def write_jsonl(records: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _batch(
    client: LLMClient,
    cache: LLMCache,
    prompts: List[str],
    workers: int,
) -> List[Tuple[Optional[str], str]]:
    return generate_batch(client, prompts, cache=cache, max_workers=workers, verbose=True)


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------

def run_llm_baseline(
    examples: List[Dict], client: LLMClient, cache: LLMCache, workers: int
) -> List[Dict]:
    print("  Building prompts...")
    prompts = [LLM_PROMPT.format(question=ex["question"]) for ex in examples]

    print(f"  Generating ({workers} workers)...")
    answers = _batch(client, cache, prompts, workers)

    records = []
    for ex, prompt, (answer, status) in zip(examples, prompts, answers):
        records.append({
            "example_id": ex["example_id"],
            "domain": ex["domain"],
            "dialogue_id": ex["dialogue_id"],
            "turn_id": ex["turn_id"],
            "question": ex["question"],
            "reference_answer": ex["reference_answer"],
            "is_unanswerable": ex.get("is_unanswerable", False),
            "is_doc_switch": ex.get("is_doc_switch", False),
            "document_id": ex["document_id"],
            "grounding": ex["grounding"],
            "prompt": prompt,
            "model_answer": answer,
            "status": status if answer is not None else "error",
            "error": None if answer is not None else status,
        })
    return records


def _build_span_index(sections: List[Dict]) -> Dict[Tuple, Dict]:
    index: Dict[Tuple, Dict] = {}
    for sec in sections:
        for sid in sec["span_ids"]:
            key = (sec["doc_id"], str(sid))
            if key not in index:
                index[key] = sec
    return index


def run_oracle_context(
    examples: List[Dict],
    client: LLMClient,
    cache: LLMCache,
    workers: int,
    prompt_template: Optional[str] = None,
) -> List[Dict]:
    print("  Building span index...")
    sections = load_sections()
    span_index = _build_span_index(sections)

    def _gold_sections(grounding: List[Dict]) -> List[Dict]:
        seen: set = set()
        result = []
        for g in grounding:
            if "doc_id" not in g or "id_sp" not in g:
                continue
            key = (g["doc_id"], str(g["id_sp"]))
            sec = span_index.get(key)
            if sec and (sec["doc_id"], sec["id_sp"]) not in seen:
                seen.add((sec["doc_id"], sec["id_sp"]))
                result.append(sec)
        return result

    def _fmt(secs: List[Dict]) -> str:
        parts = []
        for rank, s in enumerate(secs, 1):
            header = f"[{rank}] {s['title']}"
            if s.get("section_title"):
                header += f" — {s['section_title']}"
            parts.append(f"{header}\n{s['text']}")
        return "\n\n".join(parts)

    tmpl = prompt_template if prompt_template is not None else RAG_PROMPT
    contexts = [_fmt(_gold_sections(ex["grounding"])) for ex in examples]
    prompts = [tmpl.format(context=ctx, question=ex["question"])
               for ex, ctx in zip(examples, contexts)]

    print(f"  Generating ({workers} workers)...")
    answers = _batch(client, cache, prompts, workers)

    records = []
    for ex, ctx, prompt, (answer, status) in zip(examples, contexts, prompts, answers):
        is_unans = ex.get("is_unanswerable", False)
        gold_secs = _gold_sections(ex["grounding"])
        recall = 1.0 if (not is_unans and gold_secs) else None
        records.append({
            "example_id": ex["example_id"],
            "domain": ex["domain"],
            "dialogue_id": ex["dialogue_id"],
            "turn_id": ex["turn_id"],
            "question": ex["question"],
            "reference_answer": ex["reference_answer"],
            "is_unanswerable": is_unans,
            "is_doc_switch": ex.get("is_doc_switch", False),
            "document_id": ex["document_id"],
            "grounding": ex["grounding"],
            "context": ctx,
            "prompt": prompt,
            "model_answer": answer,
            "recall_at_1": recall,
            "recall_at_5": recall,
            "domain_recall": None,
            "status": status if answer is not None else "error",
            "error": None if answer is not None else status,
        })
    return records


def run_rag_retrieval(
    examples: List[Dict],
    retriever,
    client: LLMClient,
    cache: LLMCache,
    doc_domain_map: Dict,
    workers: int,
    rewriter: Optional[Any] = None,
    reranker: Optional[Any] = None,
    prompt_template: Optional[str] = None,
) -> List[Dict]:
    """Generic RAG pipeline.

    If rewriter is given, rewrites queries first (extra LLM round-trip).
    If reranker is given, retrieves RERANKER_RETRIEVE_K candidates and reranks to TOP_K.
    """

    # Phase 1: rewrite queries (batch) if needed
    questions = [ex["question"] for ex in examples]
    if rewriter is not None:
        print("  Building rewrite prompts...")
        from src.rag.query_rewriter import REWRITE_PROMPT, _format_history, HISTORY_WINDOW
        rewrite_prompts = []
        for ex in examples:
            h = ex.get("dialogue_history", [])
            if h:
                rewrite_prompts.append(
                    REWRITE_PROMPT.format(
                        history=_format_history(h),
                        question=ex["question"],
                    )
                )
            else:
                rewrite_prompts.append(None)

        real_prompts = [p for p in rewrite_prompts if p is not None]
        indices = [i for i, p in enumerate(rewrite_prompts) if p is not None]
        print(f"  Rewriting {len(real_prompts)} queries ({workers} workers)...")
        rw_answers = _batch(client, cache, real_prompts, workers)

        rewritten = list(questions)
        for i, (answer, _) in zip(indices, rw_answers):
            if answer:
                rewritten[i] = answer.strip() or questions[i]
    else:
        rewritten = questions

    # Phase 2: retrieve for all (sequential, fast)
    retrieve_k = RERANKER_RETRIEVE_K if reranker is not None else TOP_K
    print(f"  Retrieving (top-{retrieve_k})...")
    retrieved_all = []
    for q in rewritten:
        retrieved_all.append(retriever.retrieve(q, top_k=retrieve_k))

    # Phase 2b: rerank if requested
    top_reranker_scores: List[Optional[float]] = [None] * len(examples)
    if reranker is not None:
        print(f"  Reranking {len(examples)} examples (top-{retrieve_k} → top-{TOP_K})...")
        rerank_results = reranker.rerank_many(
            rewritten, retrieved_all, top_k=TOP_K
        )
        retrieved_all = [docs for docs, _ in rerank_results]
        top_reranker_scores = [score for _, score in rerank_results]
        print(
            f"  Reranking done. Truncated sections (>{RERANKER_MODEL_MAX_TOKENS} tokens): "
            f"{reranker.n_truncated}"
        )

    # Phase 3: compute recall metrics, build generation prompts
    r1_list, r5_list, dr_list = [], [], []
    for ex, retrieved in zip(examples, retrieved_all):
        r1_list.append(recall_at_k(retrieved, ex["grounding"], 1))
        r5_list.append(recall_at_k(retrieved, ex["grounding"], 5))
        dr_list.append(domain_recall_at_k(retrieved, ex["domain"], TOP_K, doc_domain_map))

    tmpl = prompt_template if prompt_template is not None else RAG_PROMPT
    contexts = [format_context(r) for r in retrieved_all]
    gen_prompts = [tmpl.format(context=ctx, question=ex["question"])
                   for ex, ctx in zip(examples, contexts)]

    # Phase 4: batch generate answers
    print(f"  Generating ({workers} workers)...")
    answers = _batch(client, cache, gen_prompts, workers)

    records = []
    for i, (ex, retrieved, ctx, prompt, r1, r5, dr, rr_score, (answer, status)) in enumerate(
        zip(
            examples, retrieved_all, contexts, gen_prompts,
            r1_list, r5_list, dr_list, top_reranker_scores, answers,
        )
    ):
        rec: Dict[str, Any] = {
            "example_id": ex["example_id"],
            "domain": ex["domain"],
            "dialogue_id": ex["dialogue_id"],
            "turn_id": ex["turn_id"],
            "question": ex["question"],
            "reference_answer": ex["reference_answer"],
            "is_unanswerable": ex.get("is_unanswerable", False),
            "is_doc_switch": ex.get("is_doc_switch", False),
            "document_id": ex["document_id"],
            "grounding": ex["grounding"],
            "context": ctx,
            "prompt": prompt,
            "model_answer": answer,
            "top_retrieval_score": retrieved[0].get("rrf_score", retrieved[0].get("score", 0.0)) if retrieved else 0.0,
            "recall_at_1": r1,
            "recall_at_5": r5,
            "domain_recall": dr,
            "status": status if answer is not None else "error",
            "error": None if answer is not None else status,
        }
        if rewriter is not None:
            rec["rewritten_query"] = rewritten[i]
        if rr_score is not None:
            rec["top_reranker_score"] = rr_score
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run all pipelines on the 500-example dev subset.")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel LLM threads (default: 8)")
    parser.add_argument("--cache-dir", default=str(CACHE_DIR))
    parser.add_argument("--subset-file", default=str(DEV_IDS_FILE))
    parser.add_argument(
        "--pipelines", nargs="+",
        default=["llm", "oracle", "bm25", "dense", "hybrid", "rewrite"],
        help=(
            "Which pipelines to run. Original: llm oracle bm25 dense hybrid rewrite. "
            "New: oracle_v2 rewrite_v2 rewrite_rerank rewrite_rerank_v2"
        ),
    )
    args = parser.parse_args()

    t0 = time.time()

    print("Loading dev subset...")
    examples = load_dev_examples()
    print(f"  {len(examples)} examples loaded\n")

    cache = LLMCache(Path(args.cache_dir))
    client = LLMClient()
    doc_domain_map = load_doc_domain_map()
    pipelines = set(args.pipelines)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- LLM baseline -------------------------------------------------------
    if "llm" in pipelines:
        print("=== LLM baseline ===")
        t = time.time()
        records = run_llm_baseline(examples, client, cache, args.workers)
        write_jsonl(records, RESULTS_DIR / "llm_baseline.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- Oracle context -----------------------------------------------------
    if "oracle" in pipelines:
        print("=== Oracle context ===")
        t = time.time()
        records = run_oracle_context(examples, client, cache, args.workers)
        write_jsonl(records, RESULTS_DIR / "oracle_context.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- RAG BM25 -----------------------------------------------------------
    if "bm25" in pipelines:
        print("=== RAG BM25 ===")
        t = time.time()
        retriever = BM25Retriever()
        records = run_rag_retrieval(examples, retriever, client, cache,
                                    doc_domain_map, args.workers)
        write_jsonl(records, RESULTS_DIR / "rag_bm25_baseline.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- RAG Dense ----------------------------------------------------------
    if "dense" in pipelines:
        print("=== RAG Dense ===")
        t = time.time()
        retriever = DenseRetriever()
        _ = retriever.corpus_size
        records = run_rag_retrieval(examples, retriever, client, cache,
                                    doc_domain_map, args.workers)
        write_jsonl(records, RESULTS_DIR / "rag_dense_baseline.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- RAG Hybrid ---------------------------------------------------------
    if "hybrid" in pipelines:
        print("=== RAG Hybrid ===")
        t = time.time()
        retriever = HybridRetriever()
        retriever.build_index()
        records = run_rag_retrieval(examples, retriever, client, cache,
                                    doc_domain_map, args.workers)
        write_jsonl(records, RESULTS_DIR / "rag_hybrid_baseline.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- RAG Hybrid + Rewrite -----------------------------------------------
    if "rewrite" in pipelines:
        print("=== RAG Hybrid + Rewrite ===")
        t = time.time()
        retriever = HybridRetriever()
        retriever.build_index()
        rewriter = QueryRewriter(client=client)
        records = run_rag_retrieval(examples, retriever, client, cache,
                                    doc_domain_map, args.workers,
                                    rewriter=rewriter)
        write_jsonl(records, RESULTS_DIR / "rag_rewrite_baseline.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- Agent prompt v2 on Oracle ------------------------------------------
    if "oracle_v2" in pipelines:
        print("=== Oracle (agent prompt v2) ===")
        t = time.time()
        few_shots = _load_few_shot_examples()
        agent_prompt = _build_agent_prompt(few_shots)
        records = run_oracle_context(examples, client, cache, args.workers,
                                     prompt_template=agent_prompt)
        write_jsonl(records, RESULTS_DIR / "oracle_context_v2.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- Agent prompt v2 on Hybrid + Rewrite --------------------------------
    if "rewrite_v2" in pipelines:
        print("=== RAG Hybrid + Rewrite (agent prompt v2) ===")
        t = time.time()
        few_shots = _load_few_shot_examples()
        agent_prompt = _build_agent_prompt(few_shots)
        retriever = HybridRetriever()
        retriever.build_index()
        rewriter = QueryRewriter(client=client)
        records = run_rag_retrieval(examples, retriever, client, cache,
                                    doc_domain_map, args.workers,
                                    rewriter=rewriter,
                                    prompt_template=agent_prompt)
        write_jsonl(records, RESULTS_DIR / "rag_rewrite_baseline_v2.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- Hybrid + Rewrite + Rerank (old prompt) -----------------------------
    if "rewrite_rerank" in pipelines:
        print("=== RAG Hybrid + Rewrite + Rerank ===")
        t = time.time()
        retriever = HybridRetriever()
        retriever.build_index()
        rewriter = QueryRewriter(client=client)
        reranker = Reranker(cache_dir=RERANKER_CACHE_DIR)
        records = run_rag_retrieval(examples, retriever, client, cache,
                                    doc_domain_map, args.workers,
                                    rewriter=rewriter,
                                    reranker=reranker)
        write_jsonl(records, RESULTS_DIR / "rag_rewrite_rerank.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    # ---- Hybrid + Rewrite + Rerank (agent prompt v2) ------------------------
    if "rewrite_rerank_v2" in pipelines:
        print("=== RAG Hybrid + Rewrite + Rerank (agent prompt v2) ===")
        t = time.time()
        few_shots = _load_few_shot_examples()
        agent_prompt = _build_agent_prompt(few_shots)
        retriever = HybridRetriever()
        retriever.build_index()
        rewriter = QueryRewriter(client=client)
        reranker = Reranker(cache_dir=RERANKER_CACHE_DIR)
        records = run_rag_retrieval(examples, retriever, client, cache,
                                    doc_domain_map, args.workers,
                                    rewriter=rewriter,
                                    reranker=reranker,
                                    prompt_template=agent_prompt)
        write_jsonl(records, RESULTS_DIR / "rag_rewrite_rerank_v2.jsonl")
        print(f"  Done in {time.time()-t:.1f}s\n")

    elapsed = time.time() - t0
    stats = cache.stats
    print(f"Total wall time : {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Cache hits      : {stats['hits']}  misses: {stats['misses']}  "
          f"hit-rate: {stats['hit_rate']*100:.0f}%")
    print(f"\nResults in: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
