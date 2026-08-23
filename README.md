# Conversational System for Retrieval-Augmented Generation (RAG)

**Author:** Danil Smirnov  
**Degree:** M.Sc. in Computer Engineering, University of Padua  
**Reference Document:** [Initial_Research_Plan_Smirnov.pdf](file:///Users/nothingtodo/VSCodeProjects/llm_rag/Initial_Research_Plan_Smirnov.pdf)

---

## 1. Project Overview

This repository hosts the research and experimental implementation for a research project focused on **Conversational Retrieval-Augmented Generation (RAG)**, progressing toward **Knowledge Graphs (KGs)**, **Graph RAG**, and **Agentic Architectures**.

The primary objective is the development and systematic evaluation of a conversational system based on Large Language Models (LLMs), capable of answering questions and maintaining goal-oriented conversations grounded in collections of documents and corporate emails.

The methodological foundation follows the approaches presented in ***Knowledge Graphs and LLMs in Action*** (with particular focus on Parts 1, 3, 5, and 6: hybrid intelligent systems, KG construction from unstructured text, Graph RAG, natural language graph querying, and QA agents).

---

## 2. Datasets & Benchmarks

The research evaluates conversational question answering and retrieval across three datasets:

1. **MultiDoc2Dial (Primary Benchmark):**
   - Goal-oriented dialogues grounded in multiple government-service documents (DMV, SSA, VA, StudentAid).
   - Gold annotations include supporting document spans, enabling rigorous evaluation of both generated answers and retrieved evidence.
2. **EnronQA (Secondary Benchmark):**
   - Question-answer pairs over a collection of corporate emails, providing an enterprise-oriented evaluation setting focused primarily on email-level retrieval.
3. **MTRAG (Optional Stress Test):**
   - Stress testing for multi-turn conversations and unanswerable / insufficient-context questions.

---

## 3. Approaches Investigated

The project develops and compares six progressive architectures:

1. **LLM-only Baseline:** Direct parametric question answering without external retrieval or structured knowledge.
2. **Retrieval-Augmented Generation (RAG):** Conventional passage/document retrieval pipeline followed by LLM answer generation.
3. **Knowledge Graph Construction:** Transformation of unstructured documents and emails into structured graphs (entity recognition, relation extraction, graph modeling, normalization, entity resolution).
4. **Knowledge Graph-based Retrieval:** Querying the KG as a structured context source for conversational question answering.
5. **Graph RAG:** Hybrid integration combining structured relational graph facts with unstructured document context.
6. **Reasoning & Agent-based Approaches:** Dynamic orchestration where an autonomous agent determines reasoning paths, constructs queries, and selects appropriate retrieval tools and sources.

---

## 4. Current Status

The project has completed **Step 3 (LLM Baseline)**:
- [x] Azure OpenAI API integration verified (`gpt-5.4-nano-smirnov` via `LLMClient`).
- [x] Secure environment configuration (`.env` template and `.gitignore`).
- [x] Modular project architecture (`src/`, `experiments/`, `tests/`, `data/`).
- [x] MultiDoc2Dial dataset integrated with a dedicated data loader (`src.data.loader`).
- [x] Structured JSONL experiment logging established (`src.evaluation.logger`).
- [x] Deterministic 50-example validation benchmark executed on MultiDoc2Dial ([experiments/results/llm_baseline.jsonl](file:///Users/nothingtodo/VSCodeProjects/llm_rag/experiments/results/llm_baseline.jsonl)).
- [ ] **Next Stage:** Step 4 — Conventional retrieval pipeline and RAG baseline.

---

## 5. Course of Action & Timeline

The planned progression follows the 10-step course of action outlined in the research plan:

| Period | Step | Focus / Milestone | Status |
| :--- | :--- | :--- | :--- |
| **Weeks 1–2** | **Step 1: Background Study** | Review *Knowledge Graphs and LLMs in Action* (Parts 1, 3, 5, 6). | Completed |
| **Weeks 2–3** | **Step 2: Dataset Analysis** | Dataset analysis and preparation of MultiDoc2Dial (and EnronQA). | Completed |
| **Weeks 3–4** | **Step 3: LLM Baseline** | LLM-only conversational baseline & evaluation pipeline on MultiDoc2Dial subset. | Completed |
| **Weeks 4–6** | **Step 4: Retrieval and RAG** | Conventional retrieval baseline (chunking, embeddings, prompt augmentation). | Up Next |
| **Weeks 6–9** | **Step 5: KG Construction** | Unstructured document & email transformation into structured Knowledge Graphs. | Planned |
| **Weeks 9–11** | **Step 6: KG-based Retrieval** | Natural language querying of Knowledge Graphs for conversational QA. | Planned |
| **Weeks 11–14** | **Step 7: Graph RAG** | Hybrid architectures combining structured graph data and textual context. | Planned |
| **Weeks 14–17** | **Step 8: Agent-based Approaches**| Autonomous agents for reasoning, query construction, and source selection. | Planned |
| **Weeks 17–19** | **Step 9: Evaluation & Comparison** | Benchmarking across answer quality, retrieval recall, and grounding. | Planned |
| **Weeks 19–22** | **Step 10: Error Analysis** | Hallucination analysis, failure modes on unanswerable questions, and research write-up. | Planned |

---

## 6. Installation & Quickstart

### 1. Python Environment Setup
Create and activate a virtual environment (Python 3.10+):

```bash
# From project root
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the template and configure your Azure OpenAI credentials:

```bash
cp .env.example .env
```

Ensure `.env` contains:
```env
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_BASE_URL=https://2026-foundry.services.ai.azure.com/openai/v1
LLM_MODEL=gpt-5.4-nano-smirnov
```

### 4. Run Scripts & Experiments

- **Basic API Connectivity Smoke Test:**
  ```bash
  python experiments/test_llm_basic.py
  ```

- **Single Query Conversational Test:**
  ```bash
  python experiments/test_llm_conversation.py
  ```

- **Run MultiDoc2Dial LLM-Only Baseline Benchmark (50 examples):**
  ```bash
  python experiments/llm_baseline.py
  ```
  Results are deterministically saved to `experiments/results/llm_baseline.jsonl`.

- **Run Automated Unit Tests:**
  ```bash
  python -m unittest discover tests
  ```

---

## 7. Project Structure

```text
llm_rag/
├── src/                          # Core reusable package modules
│   ├── llm/                      # Reusable Azure OpenAI client & wrappers
│   │   ├── client.py
│   │   └── __init__.py
│   ├── data/                     # Dataset loaders (MultiDoc2Dial, EnronQA)
│   │   ├── loader.py
│   │   └── __init__.py
│   ├── evaluation/               # Experiment logging & metrics tracking
│   │   ├── logger.py
│   │   └── __init__.py
│   ├── rag/                      # Conventional RAG components (Stage 4)
│   ├── kg/                       # Knowledge Graph construction & queries (Stages 5-6)
│   └── agents/                   # Agentic orchestration & reasoning (Stage 8)
│
├── experiments/                  # Experiment runners and benchmarks
│   ├── test_llm_basic.py         # Smoke test for API connectivity
│   ├── test_llm_conversation.py  # Single-query conversational test
│   ├── run_baseline.py           # Sample single-query runner with logging
│   ├── llm_baseline.py           # MultiDoc2Dial 50-example baseline runner
│   ├── results/                  # Benchmark evaluation outputs
│   │   └── llm_baseline.jsonl    # 50 evaluated validation examples
│   └── logs/                     # Experiment output logs (git-ignored)
│
├── tests/                        # Automated unit tests
│   ├── test_client.py            # Client configuration tests
│   └── test_data_loader.py       # MultiDoc2Dial loader & extraction tests
│
├── data/                         # Datasets directory (git-ignored)
│   └── multidoc2dial/
│
├── notebooks/                    # Research & exploratory notebooks
├── scripts/                      # Utility and preprocessing scripts
├── Initial_Research_Plan_Smirnov.pdf # Research plan
├── .env.example                  # Template for environment variables
├── .gitignore                    # Git ignore rules
├── requirements.txt              # Project dependencies
└── README.md                     # Project documentation
```