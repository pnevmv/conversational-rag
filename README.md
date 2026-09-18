# Conversational System for Retrieval-Augmented Generation (RAG)

**Author:** Danil Smirnov  
**Degree:** M.Sc. in Computer Engineering, University of Padua  
**Supervisor:** Prof. Gianmaria Silvello  
**Thesis:** [`latex_report/`](latex_report/)

---

## 1. Project Overview

This repository hosts the research and experimental implementation for a research project focused on **Conversational Retrieval-Augmented Generation (RAG)**, progressing toward **Knowledge Graphs (KGs)**, **Graph RAG**, and **Agentic Architectures**.

The primary objective is the development and systematic evaluation of a conversational system based on Large Language Models (LLMs), capable of answering questions and maintaining goal-oriented conversations grounded in collections of documents and corporate emails.

The methodological foundation follows the approaches presented in ***Knowledge Graphs and LLMs in Action*** (Negro et al., Manning 2026), with particular focus on Parts 1, 3, 5, and 6: hybrid intelligent systems, KG construction from unstructured text, Graph RAG, natural language graph querying, and QA agents.

---

## 2. Datasets & Benchmarks

| Dataset | Role | Description |
| :--- | :--- | :--- |
| **MultiDoc2Dial** | Primary | Goal-oriented dialogues grounded in government-service documents (DMV, SSA, VA, StudentAid). Gold annotations include supporting document spans, enabling evaluation of both answer quality and retrieval evidence. |
| **EnronQA** | Secondary | QA pairs over corporate emails. Enterprise-oriented setting focused primarily on email-level retrieval. |
| **MTRAG** | Optional | Stress test for multi-turn conversations and unanswerable questions. |

---

## 3. Approaches Investigated

Six progressive architectures are developed and compared:

1. **LLM-only Baseline:** Direct parametric question answering without external retrieval or structured knowledge.
2. **Retrieval-Augmented Generation (RAG):** Passage retrieval pipeline followed by LLM answer generation.
3. **Knowledge Graph Construction:** Transformation of unstructured documents and emails into structured graphs.
4. **Knowledge Graph-based Retrieval:** Querying the KG as a structured context source for conversational QA.
5. **Graph RAG:** Hybrid integration combining structured relational graph facts with unstructured document context.
6. **Reasoning & Agent-based Approaches:** Dynamic orchestration where an autonomous agent selects retrieval tools and constructs queries.

---

## 4. Current Status

### Completed

**Step 3 — LLM Baseline and Evaluation Layer**
- [x] Azure OpenAI API integration (`gpt-5.4-nano-smirnov` via `LLMClient`).
- [x] MultiDoc2Dial loader with round-robin multi-domain sampling (`src/data/loader.py`).
- [x] Exact Match, token F1, Recall@K, Domain Recall@K, and abstention metrics (`src/evaluation/metrics.py`).
- [x] Unanswerable and document-switch tagging per turn.

**Step 4 — Retrieval and RAG**
- [x] Section-level indexing: heading + following content spans as one retrieval unit (4,114 sections from 488 documents).
- [x] BM25, dense (`BAAI/bge-small-en-v1.5`), and hybrid (RRF) retrievers (`src/rag/`).
- [x] LLM-based multi-turn query rewriting (`src/rag/query_rewriter.py`).
- [x] Cross-encoder reranker (`BAAI/bge-reranker-base`, top-50 → top-5) (`src/rag/reranker.py`).
- [x] Oracle-context baseline (gold sections given directly) as the generation ceiling.
- [x] Agent-style prompt v2 with few-shot examples from the training split.
- [x] Parallel LLM runner with disk cache (`src/llm/parallel.py`, `src/llm/cache.py`).
- [x] Fixed 500-example dev subset (125/domain, seed 42) and diagnostic evaluator with bootstrap 95% CIs and paired bootstrap tests.
- [x] Thesis write-up of Steps 3–4 (`latex_report/`).

### Experiment Results

**Full validation split** (n = 4,427; 95% bootstrap CIs in [brackets])

| System | Token F1 | Recall@5 | Domain Recall@5 |
| :--- | :---: | :---: | :---: |
| LLM-only | 15.88 [15.54, 16.29] | — | — |
| RAG — BM25 | 24.11 [23.46, 24.77] | 40.61 | 65.95 |
| RAG — Dense (bge-small) | 24.58 [23.89, 25.28] | 40.96 | 70.46 |
| RAG — Hybrid (BM25 + dense, RRF) | 24.75 [24.09, 25.43] | 44.70 | 69.39 |
| RAG — Hybrid + Query Rewriting | **26.78** [26.19, 27.46] | **59.45** | **92.46** |

Query rewriting vs. hybrid: +2.03 pp F1, 95% CI [1.43, 2.57], p < 0.001 (paired bootstrap).

**Dev-500 diagnostic subset** (n = 500)

| System | Token F1 | Recall@5 | Abstain recall | False abstention |
| :--- | :---: | :---: | :---: | :---: |
| LLM-only | 16.3 | — | 19.4 | 7.7 |
| Oracle (gold sections) | 36.1 | 100.0 | 25.8 | 4.1 |
| RAG — Hybrid + Rewrite | 28.0 | 61.2 | 35.5 | 7.0 |
| RAG — Hybrid + Rewrite + Rerank | 28.2 | 67.4 | 32.3 | 6.8 |

Key findings:
- Query rewriting is the only statistically significant F1 improvement among the interventions.
- About two thirds of the 8.1 pp gap to the oracle comes from retrieval misses.
- The reranker raises Recall@5 by 6.2 pp but not F1. It gains 53 gold sections and displaces 23 previously retrieved ones; the generator fully uses the new hits.

See the thesis chapter `latex_report/chapters/rag.tex` for full analysis, and Appendix A (`latex_report/chapters/experimental_log.tex`) for the development history and supplementary results.

### In Progress

**Step 5 — Knowledge Graph Construction** (pipeline, entity resolution and graph build done on 8 pilot documents; prompt v1 and v2 annotated on 3 documents; full run pending)

The design follows *Knowledge Graphs and LLMs in Action* (ch. 5–6), with three layers: a structural layer, a metagraph of raw LLM-extracted mentions, and a KG layer of resolved entities. Thesis chapter: `latex_report/chapters/kg_construction.tex`.

- [x] Neo4j 5 Community in Docker, client with env-based config and uniqueness constraints (`src/kg/client.py`).
- [x] Structural layer, loaded idempotently (`src/kg/structure.py`): Domain → Document → Section → Span, plus `NEXT` between consecutive sections. Section ids match the RAG index (`make_section_id()`), so retrieval results map directly to graph nodes. Sections carry `is_table` (37) and `is_boilerplate` (300) flags.

  | Nodes | Count | Relationships | Count |
  | :--- | ---: | :--- | ---: |
  | Domain | 4 | HAS_DOCUMENT | 488 |
  | Document | 488 | HAS_SECTION | 4,114 |
  | Section | 4,114 | HAS_SPAN | 35,659 |
  | Span | 35,659 | NEXT | 3,626 |

- [x] Open-extraction pilot on 32 sections (`src/kg/extract.py`): 139 entity and 180 relation types, so a closed schema is needed. Schema proposal: [`experiments/kg/schema_proposal.md`](experiments/kg/schema_proposal.md).
- [x] Closed schema (`src/kg/schema.py`): 9 entity types (Service, Organization, Document, Requirement, Amount, TimeLimit, Role, Outcome, ContactPoint) and 11 relations with fixed source → target types; ALTERNATIVE_TO is symmetric.
- [x] Closed-schema extractor (`src/kg/extract_closed.py`, `src/kg/planning.py`):
  - strict JSON output, at most 15 entities per call, optional `alias`;
  - repeated texts extracted once, long texts chunked at sentence boundaries, short and boilerplate sections skipped;
  - relations that break the type rules are flagged and not loaded;
  - full run: **3,542 LLM calls** for 3,552 sections.
- [x] Quality checks on 8 whole pilot documents (90 sections):
  - **Names and evidence:** CamelCase names fell from 69% to 1.2%, and 96% of evidence quotes are verbatim.
  - **Regression tests:** 17 cases against cached model output (`tests/test_kg_extraction.py`), with 4 documented open issues.
  - **Stability:** extraction is not deterministic. Two identical runs share only 44–48% of their triples, and the deployment offers no deterministic setting (no `seed`; temperature only with reasoning effort "none").
- [x] Entity resolution (`src/kg/resolve.py`):
  - blocking by type, with rule matches (alias, acronym, form number);
  - type conflicts: majority vote, then the type that fits the relations, then a fixed priority (Document first);
  - generic vs specific: names with no shared content word, or a coordination and one of its parts, never merge (splits 7 of 14 wrong v1 clusters, 2 of 33 correct);
  - bge-small similarity plus graph signals, then LLM confirmation in batches of up to 5 candidates;
  - cannot-link constraints and value conflicts stop chained merges.
  - **Calibration:** even above a cosine of 0.95 only about half of candidate pairs are the same entity, so only rule matches merge without the LLM; the lower threshold is 0.80.
  - **Cost:** about 21k batched calls for the full corpus, against about 66k pairwise.
- [x] Graph build (`src/kg/load_neo4j.py`), idempotent per scope:
  - metagraph: `Section -MENTIONS-> Mention -REL-> Mention`;
  - KG layer: `Mention -RESOLVES_TO-> Entity -<RELATION>-> Entity`, with `support` and `section_ids`;
  - social-media ContactPoints are flagged and kept out of the KG layer.
  - **Pilot graph:** 508 mentions, 377 entities, 309 entity relations.
  - **Coverage:** 97% of in-scope validation gold sections have mentions, and in 78% an entity from the gold section is named in the question or answer (`src/kg/stats.py`, `src/kg/coverage.py`).
- [x] Pilot annotation v1 (`src/kg/annotation.py`) of 140 extracted and 33 missed triples from 3 pilot documents, and of 47 entity clusters. Labels and missing triples were drafted by an LLM and reviewed by the author. These are pilot numbers that guide the revisions, not the quality of the final KG:

  | | Score (95% CI) |
  | :--- | :--- |
  | Triple precision, single run | **46.4%** [38.4, 54.7] |
  | Triple recall, single run | **66.3%** [56.5, 74.9] (F1 54.6%) |
  | Precision of triples found by both of two runs | **67.3%** [53.4, 78.8] |
  | Precision of triples found by one run only | 35.2% [26.1, 45.4] |
  | Entity-cluster precision | 70.2% [56.0, 81.3] (rule/normalisation merges 10/10, LLM-confirmed 23/37) |

  The main error patterns are documents typed as services (which reverses REQUIRES), non-requirements as REQUIRES targets, locations typed as roles, and missed alternatives (none of 3 found) and fees (none of 2 found).
- [x] Extraction prompt v2 (`--prompt-version v2`; v1 unchanged), with rules for the v1 error patterns, guidance for alternatives, fees and procedure stages, and three worked examples from documents outside the pilot. Evaluated on the same 3 documents ([`v1_v2_comparison.md`](experiments/kg/v1_v2_comparison.md), paired section bootstrap):

  | | Precision | Recall (98 gold) | Recall (pooled, 121) |
  | :--- | ---: | ---: | ---: |
  | v1, single run | 46.4 | 66.3 | 53.7 |
  | v2, single run | 53.7 | 41.8 | 52.9 |
  | v2, triples both runs agree on | **72.1** | 31.6 | 34.7 |

  - **Precision:** up 7 points (not significant), still short of the 65–70% target for a single run.
  - **Recall:** the drop against the 98 gold facts is mostly an artefact of building the gold set from v1's output; pooled recall is unchanged.
  - **Relations:** alternatives are now found (ALTERNATIVE_TO P 75%, R 67%), but contact points are mostly lost and fees are still missing.
  - **Run agreement:** v2 triples found by one run only are 35.5% precise, so intersection would be the rule's choice, at the cost of a third of the facts.
- [ ] Decide between v2 with two-run intersection and a further prompt revision, and how to treat places ("outside of the United States"); then the full extraction, entity resolution, and the full KG build.

Reports: [`pilot2_report.md`](experiments/kg/pilot2_report.md) (closed-schema pilot), [`pilot3_report.md`](experiments/kg/pilot3_report.md) (pre-run checks, stability, entity resolution) and [`build_pilot_report.md`](experiments/kg/build_pilot_report.md) (graph build, statistics, coverage, example queries).

---

## 5. Course of Action & Timeline

| Period | Step | Focus / Milestone | Status |
| :--- | :--- | :--- | :--- |
| **Weeks 1–2** | **Step 1: Background Study** | Review *Knowledge Graphs and LLMs in Action* (Parts 1, 3, 5, 6). | Completed |
| **Weeks 2–3** | **Step 2: Dataset Analysis** | Dataset analysis and preparation of MultiDoc2Dial (and EnronQA). | Completed |
| **Weeks 3–4** | **Step 3: LLM Baseline** | LLM-only baseline, evaluation pipeline, EM + token F1 metrics. | Completed |
| **Weeks 4–6** | **Step 4: Retrieval and RAG** | BM25, dense, hybrid, query rewriting, reranking, oracle ceiling; full-split and dev-500 evaluation. | Completed |
| **Weeks 6–9** | **Step 5: KG Construction** | Unstructured document transformation into structured Knowledge Graphs. | In progress |
| **Weeks 9–11** | **Step 6: KG-based Retrieval** | Natural language querying of Knowledge Graphs for conversational QA. | Planned |
| **Weeks 11–14** | **Step 7: Graph RAG** | Hybrid architectures combining structured graph data and textual context. | Planned |
| **Weeks 14–17** | **Step 8: Agent-based Approaches** | Autonomous agents for reasoning, query construction, and source selection. | Planned |
| **Weeks 17–19** | **Step 9: Evaluation & Comparison** | Benchmarking across answer quality, retrieval recall, and grounding. | Planned |
| **Weeks 19–22** | **Step 10: Error Analysis** | Hallucination analysis, failure modes on unanswerable questions, and research write-up. | Planned |

---

## 6. Installation & Quickstart

### 1. Python Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Set in `.env`:
```env
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_BASE_URL=https://2026-foundry.services.ai.azure.com/openai/v1
LLM_MODEL=gpt-5.4-nano-smirnov

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_me_min_8_chars
```

### 4. Start Neo4j (for the KG steps)

```bash
docker compose up -d neo4j      # browser at http://localhost:7474
```

### 5. Run Experiments

| Command | Description |
| :--- | :--- |
| `python experiments/llm_baseline.py` | LLM-only baseline |
| `python experiments/rag_baseline.py` | BM25 RAG baseline |
| `python experiments/rag_dense_baseline.py` | Dense RAG baseline (bge-small; builds index on first run) |
| `python experiments/rag_hybrid_baseline.py` | Hybrid RAG baseline (BM25 + dense, RRF) |
| `python experiments/rag_rewrite_baseline.py` | Hybrid + query rewriting baseline |
| `python experiments/oracle_context.py` | Oracle-context baseline (gold sections) |
| `python experiments/run_dev_subset.py --workers 12` | All pipelines on the dev-500 subset, in parallel with disk cache |
| `python experiments/evaluate_diagnostics.py` | Diagnostic evaluation with bootstrap CIs and paired tests |
| `python experiments/evaluate_baseline.py --input experiments/results/<file>.jsonl` | Evaluate any result file |
| `python -m src.kg.structure` | Load the KG structural layer into Neo4j (idempotent) |
| `python -m src.kg.extract` | Open-extraction pilot (32 sections, cached) |
| `python -m src.kg.extract_closed` | Closed-schema extraction of the 8 pilot documents (`--regression`, `--tables` for the other sets) |
| `python -m src.kg.stability` | Compare two extraction runs (entity and triple overlap) |
| `python -m src.kg.annotation export \| stability \| score \| score-er \| carry` | Annotation sheets, run-agreement file, triple precision/recall/F1, entity-cluster precision, label carry-over to a new extraction |
| `python -m src.kg.extract_closed --annotated --prompt-version v2` | Extract the 3 annotated documents with prompt v2 |
| `python -m src.kg.compare_prompts` | v1 vs v2: precision, recall (fixed and pooled), F1 per relation and document, bootstrap CIs, run agreement |
| `python -m src.kg.resolve calibrate \| run \| estimate` | Entity resolution: threshold calibration, pilot run, full-corpus cost estimate |
| `python -m src.kg.load_neo4j` | Load the pilot metagraph and KG layer into Neo4j (idempotent per scope) |
| `python -m src.kg.stats --scope pilot` | Per-layer counts, degree distribution, components, top entities |
| `python -m src.kg.coverage --scope pilot [--examples validation]` | Coverage of QA gold sections by the graph |
| `python -m pytest tests` | Run all tests (101 pass, 4 expected failures documenting open extraction issues) |

### 6. Note on Dense Index

The first run of `rag_dense_baseline.py` downloads `BAAI/bge-small-en-v1.5` (~130 MB) and builds the embedding index (~27 seconds on Apple MPS). The index is cached to `data/cache/` and reused on all subsequent runs.

---

## 7. Project Structure

```text
llm_rag/
├── src/
│   ├── llm/                      # Azure OpenAI client, parallel runner, disk cache
│   │   ├── client.py
│   │   ├── parallel.py
│   │   └── cache.py
│   ├── data/                     # MultiDoc2Dial loader (sections, QA pairs, section ids)
│   │   └── loader.py
│   ├── evaluation/               # Metrics (EM, F1, Recall@K, abstention) and logger
│   │   ├── metrics.py
│   │   └── logger.py
│   ├── rag/                      # Retrieval components
│   │   ├── retriever.py          # BM25 retriever
│   │   ├── dense_retriever.py    # Dense retriever (bge-small)
│   │   ├── hybrid_retriever.py   # Hybrid retriever (BM25 + dense, RRF)
│   │   ├── query_rewriter.py     # LLM-based multi-turn query rewriter
│   │   └── reranker.py           # Cross-encoder reranker (bge-reranker-base)
│   ├── kg/                       # Knowledge Graph (Step 5)
│   │   ├── client.py             # Neo4j client (env config, constraints, counts)
│   │   ├── structure.py          # Structural layer loader
│   │   ├── extract.py            # Open entity/relation extraction (schema-design pilot)
│   │   ├── pilot_stats.py        # Open-pilot aggregation and evidence check
│   │   ├── schema.py             # Closed schema: types, relation rules, JSON schema
│   │   ├── planning.py           # Extraction units: skipping, deduplication, chunking
│   │   ├── extract_closed.py     # Closed-schema extraction and post-processing
│   │   ├── pilot2_stats.py       # Closed-pilot quality and overlap statistics
│   │   ├── stability.py          # Run-to-run comparison
│   │   ├── annotation.py         # Annotation export, label carry-over, precision/recall scoring
│   │   ├── compare_prompts.py    # Prompt v1 vs v2 evaluation
│   │   ├── resolve.py            # Entity resolution
│   │   ├── load_neo4j.py         # Metagraph and KG-layer loader
│   │   ├── stats.py              # Graph statistics per scope
│   │   └── coverage.py           # QA coverage of the graph
│   └── agents/                   # Agentic orchestration (planned)
│
├── experiments/
│   ├── llm_baseline.py           # LLM-only baseline runner
│   ├── rag_*_baseline.py         # BM25 / dense / hybrid / rewrite RAG runners
│   ├── oracle_context.py         # Oracle-context baseline (generation ceiling)
│   ├── create_dev_subset.py      # Builds the fixed dev-500 subset
│   ├── run_dev_subset.py         # Parallel runner for all pipelines on dev-500
│   ├── evaluate_baseline.py      # Per-file evaluation (EM, F1, recall, abstention)
│   ├── evaluate_diagnostics.py   # Bootstrap CIs, hit/miss F1, paired tests
│   ├── results/                  # Result JSONL + evaluation JSON (full split, dev_500/)
│   └── kg/                       # KG pilot outputs, reports, annotation sheets, ER results
│
├── latex_report/                 # Thesis (LuaLaTeX, unipd-thesis-modern)
├── docker-compose.yml            # Neo4j 5 Community
│
├── tests/
│   ├── test_client.py
│   ├── test_data_loader.py
│   ├── test_evaluation_metrics.py
│   ├── test_retriever.py
│   ├── test_dense_retriever.py
│   ├── test_hybrid_retriever.py
│   ├── test_query_rewriter.py
│   ├── test_kg_extraction.py     # Prompt regression tests (read cached model output)
│   ├── test_kg_resolve.py        # Type-conflict resolution
│   └── test_kg_build.py          # Loader tests (need Neo4j and the pilot files)
│
├── data/
│   ├── multidoc2dial/            # Dataset files (git-ignored)
│   ├── dev_500_ids.json          # Fixed dev-500 subset ids
│   └── cache/                    # Dense index cache (git-ignored)
│
├── .env.example
├── requirements.txt
└── README.md
```
