# Conversational RAG and Knowledge Graphs

M.Sc. thesis project in Computer Engineering at the University of Padua.
Author: Danil Smirnov. Supervisor: Prof. Gianmaria Silvello.
The thesis itself is in `latex_report/`.

The project studies conversational question answering over document collections. It starts from an LLM-only baseline, builds a RAG pipeline, then constructs a knowledge graph from the documents and tests whether retrieval over the graph helps. Later steps will look at Graph RAG and agent-based approaches. The main benchmark is MultiDoc2Dial (goal-oriented dialogues grounded in DMV, SSA, VA and StudentAid documents). EnronQA and MTRAG are secondary/optional datasets.

The methodology loosely follows *Knowledge Graphs and LLMs in Action* (Negro et al., Manning).

## Status

Steps 1–6 are done; Step 7 (Graph RAG) is next. All LLM calls go to an Azure OpenAI deployment (`gpt-5.4-nano-smirnov`).

### Step 3–4: LLM baseline and RAG

Documents are split into sections (heading plus the following spans, 4,114 sections from 488 documents). Retrieval uses BM25, bge-small dense embeddings, and a hybrid of the two with RRF. Follow-up questions are rewritten into standalone queries with an LLM, and a bge-reranker cross-encoder optionally reranks the top 50. Most comparisons are on a fixed 500-example dev subset (125 per domain).

Results on the full validation split (4,427 examples), token F1 with 95% bootstrap CI:

| System | F1 | Recall@5 |
| --- | --- | --- |
| LLM only | 15.9 [15.5, 16.3] | - |
| BM25 | 24.1 [23.5, 24.8] | 40.6 |
| Dense | 24.6 [23.9, 25.3] | 41.0 |
| Hybrid | 24.8 [24.1, 25.4] | 44.7 |
| Hybrid + rewrite | 26.8 [26.2, 27.5] | 59.5 |

On dev-500, the oracle (gold sections in the prompt) reaches 36.1 F1 and the best pipeline (hybrid + rewrite + rerank) 28.0. Query rewriting is the only change with a significant F1 gain. The reranker raises Recall@5 from 61.2 to 67.4 but not F1. Roughly two thirds of the gap to the oracle comes from retrieval misses. See `latex_report/chapters/rag.tex`.

### Step 5: Knowledge graph construction

The graph has three layers in Neo4j: a structural layer (domain, document, section, span), a metagraph of LLM-extracted mentions, and an entity layer after entity resolution. Extraction uses a closed schema with 9 entity types and 11 relations, which came out of a small open-extraction pilot.

Some things that came up along the way:

- Extraction is not deterministic. Two runs with the same settings share only 44–48% of their triples.
- A pilot annotation of 3 documents gave 44% precision and 65% recall for one run with prompt v1, and 67% precision for triples that two runs agree on. The labels were drafted with an LLM and checked by me.
- Prompt v2 raised precision to about 54%. v2.1 added contact points, fees and a few deterministic post-filters, and was used for the full build.
- Embedding similarity alone is not enough for entity resolution (about half of the pairs above cosine 0.95 are different entities), so merges go through rules or a batched LLM judge, with a guard against generic "hub" names.

The full graph has 14,731 entities and 13,277 relations (12,970 LLM calls, about an hour). In 96.6% of dev-500 questions the gold section has at least one entity. Precision on a control sample of 30 triples from unseen documents is 53% (33% if borderline cases count as wrong). Details are in `latex_report/chapters/kg_construction.tex` and `experiments/kg/full_build_report.md`.

### Step 6: Retrieval over the graph

The user turn (rewritten as in Step 4) is linked to graph entities with bge-small and BM25 over entity names. The top-10 entities contain an entity of the gold section for 70% of dev-500 questions. Skipping high-degree entities made this worse, so they are kept.

From the linked entities I tried several ways to build the context, all with the same generator and prompt as Step 4:

| Pipeline (dev-500) | Recall@5 | F1 | ΔF1 vs Step 4 |
| --- | --- | --- | --- |
| Step 4 best (hybrid + rewrite + rerank) | 67.4 | 28.0 | - |
| A: sections reached through entities | 34.6 | 24.5 | -3.5 [-5.1, -1.9] |
| A with 1-hop expansion | 36.6 | 23.5 | -4.5 [-6.3, -2.8] |
| B: graph facts only | 37.2 | 25.4 | -2.7 [-4.4, -0.8] |
| C: A fused with Step 4, reranked | 67.6 | 27.6 | -0.5 [-1.2, 0.1] |
| D: A's candidates reranked | 58.8 | 26.4 | -1.6 [-2.9, -0.4] |
| E: Step 4 sections + graph facts | 67.4 | 29.2 | +1.1 [-0.3, 2.5] |
| E with random facts (control) | 67.4 | 29.1 | +1.0 [-0.3, 2.4] |

Retrieval over the graph alone is clearly worse than passage retrieval. Linking works reasonably well, but entity overlap can't rank the many sections that the linked entities point to. Adding graph facts to the Step 4 context (E) looks like a small gain, but random facts from the same domain give the same overall number, mostly because extra context makes the model abstain more often. On answerable questions the real facts do help (+0.9), and where they come from the gold section they beat random facts by 1.8 points. So the graph is useful only when its facts actually reach the answer. That is the starting point for Graph RAG.

The reports are `experiments/kg_rag/phase1_report.md` and `experiments/kg_rag/phase2_report.md`, and the thesis chapter is `latex_report/chapters/kg_retrieval.tex`.

## Plan

1. Background study
2. Dataset analysis
3. LLM baseline and evaluation
4. Retrieval and RAG
5. KG construction
6. KG-based retrieval
7. Graph RAG (next)
8. Agent-based approaches
9. Evaluation and comparison
10. Error analysis and write-up

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the Azure key and NEO4J_PASSWORD
docker compose up -d neo4j
```

`.env` needs `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_BASE_URL`, `LLM_MODEL` and the `NEO4J_*` settings (see `.env.example`).

The first dense run downloads bge-small and builds the index in `data/cache/` (about half a minute).

## Running things

RAG experiments:

```bash
python experiments/run_dev_subset.py --workers 12        # all pipelines on dev-500 (cached LLM calls)
python experiments/evaluate_diagnostics.py               # CIs, hit/miss F1, paired tests
python experiments/rag_rewrite_baseline.py               # single pipelines on the full split
```

Knowledge graph:

```bash
python -m src.kg.structure                                # structural layer
python -m src.kg.extract_closed --all --prompt-version v2.1 --output experiments/kg/full_v21_extraction.jsonl
python -m src.kg.resolve run --input experiments/kg/full_v21_extraction.jsonl --prefix er_full
python -m src.kg.load_neo4j --scope full --run-id full_v21 \
    --extraction experiments/kg/full_v21_extraction.jsonl --resolution experiments/kg/er_full_mentions.jsonl
python -m src.kg.stats --scope full
python -m src.kg.coverage --scope full
```

Retrieval over the graph:

```bash
python -m src.kg_rag.graph_index --scope full
python -m src.kg_rag.eval_linking
python -m src.kg_rag.run_qa
python -m src.kg_rag.eval_qa
```

Tests: `python -m pytest tests` (152 pass, 4 expected failures that document open extraction issues).

## Layout

```text
src/llm/          LLM client, parallel runner, disk cache
src/data/         MultiDoc2Dial loader
src/evaluation/   metrics
src/rag/          BM25, dense, hybrid, query rewriter, reranker
src/kg/           schema, extraction, entity resolution, Neo4j loaders, annotation tools
src/kg_rag/       entity linking and graph retrievers
experiments/      runners, evaluation scripts, reports (kg/, kg_rag/)
latex_report/     thesis
tests/
```

Raw outputs (`*.jsonl`), caches and the dataset are not tracked.
