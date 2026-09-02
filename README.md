# Conversational System for Retrieval-Augmented Generation (RAG)

**Author:** Danil Smirnov  
**Degree:** M.Sc. in Computer Engineering, University of Padua  
**Supervisor:** Prof. Gianmaria Silvello  
**Reference Document:** [Initial_Research_Plan_Smirnov.pdf](Initial_Research_Plan_Smirnov.pdf)

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

**Step 3 — LLM Baseline**
- [x] Azure OpenAI API integration (`gpt-5.4-nano-smirnov` via `LLMClient`).
- [x] MultiDoc2Dial dataset loader (`src/data/loader.py`).
- [x] JSONL experiment logger (`src/evaluation/logger.py`).
- [x] Deterministic 50-example benchmark on MultiDoc2Dial validation split.
- [x] Result: Token F1 **7.53%**, Exact Match 0.00%.

**Step 3.5 — Evaluation Layer**
- [x] Reusable Exact Match and token-level F1 metrics (`src/evaluation/metrics.py`).
- [x] Evaluation script for any experiment JSONL (`experiments/evaluate_baseline.py`).
- [x] 19 unit tests for evaluation metrics.

**Step 4 — Retrieval and RAG**
- [x] Section-level indexing: heading + all following content spans joined as one retrieval unit (`src/data/loader.py`: `load_sections()`).
- [x] BM25 retriever over 4,114 sections (`src/rag/retriever.py`).
  - Result: Token F1 **20.68%**, Recall@5 40.00%.
- [x] Dense retriever using `BAAI/bge-small-en-v1.5` embeddings, cosine similarity, disk-cached index (`src/rag/dense_retriever.py`).
  - Result: Token F1 **19.44%**, Recall@5 42.00%.
- [x] Hybrid retriever combining BM25 + dense via Reciprocal Rank Fusion (`src/rag/hybrid_retriever.py`).
  - Result: Token F1 **19.79%**, Recall@5 46.00%.
- [x] Multi-turn query rewriting: LLM rewrites each user turn into a standalone query using dialogue history (`src/rag/query_rewriter.py`).
  - Result: Token F1 **23.59%**, Recall@5 **68.00%** (+22 pp over hybrid alone).
- [x] 10 unit tests for BM25, 10 for dense, 9 for hybrid/RRF, 12 for query rewriter (64 total).

### Experiment Results (MultiDoc2Dial validation, 50 examples)

| Experiment | Token F1 | Recall@1 | Recall@5 |
| :--- | :---: | :---: | :---: |
| LLM-only baseline | 7.53% | — | — |
| RAG — BM25 | 20.68% | 30.00% | 40.00% |
| RAG — Dense (bge-small) | 19.44% | 24.00% | 42.00% |
| RAG — Hybrid (BM25 + dense, RRF) | 19.79% | 32.00% | 46.00% |
| RAG — Hybrid + Query Rewriting | **23.59%** | **40.00%** | **68.00%** |

See [`experiments_description.txt`](experiments_description.txt) for full analysis.

### Next Stage

**Step 5:** Knowledge Graph construction — transform MultiDoc2Dial documents into structured graphs for entity- and relation-based retrieval.

---

## 5. Course of Action & Timeline

| Period | Step | Focus / Milestone | Status |
| :--- | :--- | :--- | :--- |
| **Weeks 1–2** | **Step 1: Background Study** | Review *Knowledge Graphs and LLMs in Action* (Parts 1, 3, 5, 6). | Completed |
| **Weeks 2–3** | **Step 2: Dataset Analysis** | Dataset analysis and preparation of MultiDoc2Dial (and EnronQA). | Completed |
| **Weeks 3–4** | **Step 3: LLM Baseline** | LLM-only baseline, evaluation pipeline, EM + token F1 metrics. | Completed |
| **Weeks 4–6** | **Step 4: Retrieval and RAG** | BM25 and dense retrieval baselines; hybrid and multi-turn query rewriting. | Completed |
| **Weeks 6–9** | **Step 5: KG Construction** | Unstructured document transformation into structured Knowledge Graphs. | Planned |
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
```

### 4. Run Experiments

| Command | Description |
| :--- | :--- |
| `python experiments/llm_baseline.py` | LLM-only baseline (50 examples) |
| `python experiments/rag_baseline.py` | BM25 RAG baseline |
| `python experiments/rag_dense_baseline.py` | Dense RAG baseline (bge-small; builds index on first run) |
| `python experiments/rag_hybrid_baseline.py` | Hybrid RAG baseline (BM25 + dense, RRF) |
| `python experiments/rag_rewrite_baseline.py` | Hybrid + query rewriting baseline |
| `python experiments/evaluate_baseline.py --input experiments/results/<file>.jsonl` | Evaluate any result file |
| `python -m unittest discover tests` | Run all unit tests (64 tests) |

### 5. Note on Dense Index

The first run of `rag_dense_baseline.py` downloads `BAAI/bge-small-en-v1.5` (~130 MB) and builds the embedding index (~27 seconds on Apple MPS). The index is cached to `data/cache/` and reused on all subsequent runs.

---

## 7. Project Structure

```text
llm_rag/
├── src/
│   ├── llm/                      # Azure OpenAI client
│   │   └── client.py
│   ├── data/                     # MultiDoc2Dial loader
│   │   └── loader.py
│   ├── evaluation/               # Metrics (EM, token F1) and experiment logger
│   │   ├── metrics.py
│   │   └── logger.py
│   ├── rag/                      # Retrieval components
│   │   ├── retriever.py          # BM25 retriever
│   │   ├── dense_retriever.py    # Dense retriever (bge-small)
│   │   ├── hybrid_retriever.py   # Hybrid retriever (BM25 + dense, RRF)
│   │   └── query_rewriter.py     # LLM-based multi-turn query rewriter
│   ├── kg/                       # Knowledge Graph (Stage 5–6, planned)
│   └── agents/                   # Agentic orchestration (Stage 8, planned)
│
├── experiments/
│   ├── llm_baseline.py           # LLM-only baseline runner
│   ├── rag_baseline.py           # BM25 RAG baseline runner
│   ├── rag_dense_baseline.py     # Dense RAG baseline runner
│   ├── rag_hybrid_baseline.py    # Hybrid RAG baseline runner (BM25 + dense, RRF)
│   ├── rag_rewrite_baseline.py   # Hybrid + query rewriting baseline runner
│   ├── evaluate_baseline.py      # Evaluation script (EM + token F1)
│   ├── test_llm_basic.py         # API connectivity smoke test
│   ├── test_llm_conversation.py  # Single-query conversational test
│   └── results/
│       ├── llm_baseline.jsonl
│       ├── llm_baseline_evaluation.json
│       ├── rag_baseline.jsonl
│       ├── rag_baseline_evaluation.json
│       ├── rag_dense_baseline.jsonl
│       ├── rag_dense_baseline_evaluation.json
│       ├── rag_hybrid_baseline.jsonl
│       ├── rag_hybrid_baseline_evaluation.json
│       ├── rag_rewrite_baseline.jsonl
│       └── rag_rewrite_baseline_evaluation.json
│
├── tests/
│   ├── test_client.py
│   ├── test_data_loader.py
│   ├── test_evaluation_metrics.py
│   ├── test_retriever.py
│   ├── test_dense_retriever.py
│   ├── test_hybrid_retriever.py
│   └── test_query_rewriter.py
│
├── data/
│   ├── multidoc2dial/            # Dataset files (git-ignored)
│   └── cache/                    # Dense index cache (git-ignored)
│
├── experiments_description.txt   # Detailed experiment analysis and results
├── Initial_Research_Plan_Smirnov.pdf
├── .env.example
├── requirements.txt
└── README.md
```
