# Conversational RAG and Knowledge Graphs - M.Sc. Thesis

This repository contains the code, experiments and thesis for my M.Sc. thesis on conversational question answering over document collections, starting from Retrieval-Augmented Generation (RAG) and moving towards Knowledge Graphs (KGs), Graph RAG and agent-based approaches.

The thesis is part of the

* [Master Degree in Computer Engineering](https://degrees.dei.unipd.it/master-degrees/computer-engineering/) of the [Department of Information Engineering](https://www.dei.unipd.it/en/), [University of Padua](https://www.unipd.it/en/), Italy.

Supervisor: Prof. Gianmaria Silvello.

The main benchmark is [MultiDoc2Dial](https://doc2dial.github.io/multidoc2dial/), a dataset of goal-oriented dialogues grounded in government-service documents from four domains (DMV, SSA, VA, StudentAid). EnronQA and MTRAG are kept as secondary datasets. The methodology follows *Knowledge Graphs and LLMs in Action* (Negro et al., Manning), mostly Parts 1, 3, 5 and 6.

## Author
- Danil Smirnov - danil.smirnov@studenti.unipd.it

## Organisation of the repository

The repository is organised as follows:

* `src`: the source code. `llm` is the Azure OpenAI client with a parallel runner and a disk cache, `data` the MultiDoc2Dial loader, `evaluation` the metrics, `rag` the retrievers, query rewriter and reranker, `kg` the knowledge graph construction (schema, extraction, entity resolution, Neo4j loaders) and `kg_rag` the retrieval over the graph.
* `experiments`: the scripts that run the pipelines and evaluate them, plus the reports of the KG work in `experiments/kg` and `experiments/kg_rag`.
* `latex_report`: the thesis (LuaLaTeX, unipd-thesis-modern template).
* `tests`: unit and regression tests.
* `data`: the dataset (not tracked), the ids of the fixed dev-500 subset and the dense index cache.

Raw model outputs (`*.jsonl`) and LLM caches are not tracked; they can be regenerated with the scripts below.

## Current status

| Step | Topic | Status |
| :--- | :--- | :--- |
| 1 | Background study | done |
| 2 | Dataset analysis | done |
| 3 | LLM-only baseline and evaluation | done |
| 4 | Retrieval and RAG | done |
| 5 | Knowledge graph construction | done |
| 6 | Retrieval over the knowledge graph | done |
| 7 | Graph RAG | next |
| 8 | Agent-based approaches | planned |
| 9 | Evaluation and comparison | planned |
| 10 | Error analysis and write-up | planned |

All LLM calls use an Azure OpenAI deployment (`gpt-5.4-nano-smirnov`).

### Steps 3-4: LLM baseline and RAG

Documents are split into sections (a heading plus the following spans, 4,114 sections from 488 documents). Retrieval uses BM25, dense embeddings (`BAAI/bge-small-en-v1.5`) and a hybrid of the two with Reciprocal Rank Fusion. Follow-up questions are rewritten by the LLM into standalone queries, and a cross-encoder (`BAAI/bge-reranker-base`) can rerank the top 50 sections. Ablations are run on a fixed subset of 500 validation examples (125 per domain, seed 42).

Token F1 on the full validation split (4,427 examples, 95% bootstrap CI):

| System | Token F1 | Recall@5 | Domain Recall@5 |
| :--- | :---: | :---: | :---: |
| LLM only | 15.9 [15.5, 16.3] | - | - |
| BM25 | 24.1 [23.5, 24.8] | 40.6 | 66.0 |
| Dense | 24.6 [23.9, 25.3] | 41.0 | 70.5 |
| Hybrid | 24.8 [24.1, 25.4] | 44.7 | 69.4 |
| Hybrid + query rewriting | **26.8** [26.2, 27.5] | **59.5** | **92.5** |

Query rewriting is the only change with a significant F1 gain (+2.0 points over hybrid, p < 0.001). On dev-500 the oracle (gold sections given to the model) reaches 36.1 F1, and about two thirds of the gap to the best pipeline comes from retrieval misses. The reranker raises Recall@5 from 61.2 to 67.4 but not F1 (28.2 vs 28.0). More in `latex_report/chapters/rag.tex`.

### Step 5: Knowledge graph construction

The graph is stored in Neo4j in three layers: a structural layer (domain, document, section, span), a metagraph with the mentions extracted by the LLM, and an entity layer obtained by entity resolution. Extraction uses a closed schema with 9 entity types and 11 relation types, designed after a small open-extraction pilot.

A few things learned on the way:

* extraction is not deterministic: two runs with the same settings share only 44-48% of their triples;
* on a pilot annotation of 3 documents, one run with the first prompt has 44% precision and 65% recall (67% precision for the triples two runs agree on); the second prompt raises precision to about 54%;
* embedding similarity is not enough to merge entities (about half of the pairs above cosine 0.95 are different entities), so merges go through rules or a batched LLM judge, with a guard against generic "hub" names.

| Full graph (prompt v2.1) | |
| :--- | :--- |
| Entities | 14,731 (from 28,782 mentions) |
| Entity relations | 13,277 |
| dev-500 gold sections with an entity | 96.6% |
| Precision on a control sample (30 triples) | 53% (33% strict) |
| Cost | 12,970 LLM calls, about 1 hour |

The labels of the annotations were drafted with an LLM and reviewed by me. Details are in `latex_report/chapters/kg_construction.tex` and `experiments/kg/full_build_report.md`.

### Step 6: Retrieval over the knowledge graph

The user turn, rewritten as in Step 4, is linked to graph entities (dense + BM25 over entity names). The top-10 entities include an entity of the gold section for 70% of the dev-500 questions. Starting from the linked entities, several retrievers were compared with the best Step 4 pipeline, using the same generator and prompt:

| Pipeline (dev-500) | Recall@5 | Token F1 | ΔF1 vs Step 4 [95% CI] |
| :--- | :---: | :---: | :---: |
| Step 4 best (hybrid + rewrite + rerank) | 67.4 | 28.0 | - |
| A: sections reached through entities | 34.6 | 24.5 | -3.5 [-5.1, -1.9] |
| A with 1-hop expansion | 36.6 | 23.5 | -4.5 [-6.3, -2.8] |
| B: graph facts only | 37.2 | 25.4 | -2.7 [-4.4, -0.8] |
| C: A fused with Step 4, reranked | 67.6 | 27.6 | -0.5 [-1.2, 0.1] |
| D: A's candidates reranked | 58.8 | 26.4 | -1.6 [-2.9, -0.4] |
| E: Step 4 sections + graph facts | 67.4 | **29.2** | +1.1 [-0.3, 2.5] |
| E with random facts (control) | 67.4 | 29.1 | +1.0 [-0.3, 2.4] |

Retrieval over the graph alone is worse than passage retrieval: linking works, but entity overlap cannot rank the many sections the entities point to. Adding graph facts to the Step 4 context (E) gives a small gain, but random facts from the same domain give the same overall number, mostly because the extra context makes the model abstain more. On answerable questions the real facts do help (+0.9), and where they come from the gold section they beat random facts by 1.8 points. This is the starting point for Graph RAG. Reports: `experiments/kg_rag/phase1_report.md` and `experiments/kg_rag/phase2_report.md`.

---

## Quickstart - RAG on dev-500

You need Python 3 (developed with 3.14) and access to an Azure OpenAI deployment.

### 1. Set up the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Download the data

Download MultiDoc2Dial v1.0 from the [project page](https://doc2dial.github.io/multidoc2dial/) and unpack it into `data/multidoc2dial/`, so that the folder contains:

```text
data/multidoc2dial/multidoc2dial_doc.json
data/multidoc2dial/multidoc2dial_dial_train.json
data/multidoc2dial/multidoc2dial_dial_validation.json
data/multidoc2dial/multidoc2dial_dial_test.json
```

The ids of the dev-500 subset are already in `data/dev_500_ids.json`.

### 3. Configure

```bash
cp .env.example .env
```

Then set in `.env`:

```env
AZURE_OPENAI_API_KEY=<your key>
AZURE_OPENAI_BASE_URL=https://<your resource>.services.ai.azure.com/openai/v1
LLM_MODEL=gpt-5.4-nano-smirnov
```

### 4. Run the pipelines

```bash
python experiments/run_dev_subset.py --workers 12 \
  --pipelines llm oracle_v2 rewrite_v2 rewrite_rerank_v2
```

The first run downloads bge-small and builds the dense index in `data/cache/` (about half a minute). LLM answers are cached in `experiments/cache/`, so re-runs are free. Results are written to `experiments/results/dev_500/`.

### 5. Evaluate

```bash
python experiments/evaluate_diagnostics.py \
  --inputs experiments/results/dev_500/*.jsonl
```

Expected token F1 for `rag_rewrite_rerank_v2`: ~28.0.

The single pipelines on the full validation split can be run with `experiments/llm_baseline.py`, `experiments/rag_baseline.py`, `experiments/rag_dense_baseline.py`, `experiments/rag_hybrid_baseline.py`, `experiments/rag_rewrite_baseline.py` and `experiments/oracle_context.py`.

---

## Knowledge graph

### Neo4j

The graph is stored in Neo4j 5 Community, run with Docker. Add the connection settings to `.env`:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<at least 8 characters>
```

and start the container:

```bash
docker compose up -d neo4j
```

The browser is at http://localhost:7474.

### Building the full graph

Run all commands from the repository root.

1. Load the structural layer (domains, documents, sections, spans):

```bash
python -m src.kg.structure
```

2. Extract entities and relations from the whole corpus (about 3,500 LLM calls, cached):

```bash
python -m src.kg.extract_closed --all --prompt-version v2.1 \
  --output experiments/kg/full_v21_extraction.jsonl
```

3. Resolve the entities:

```bash
python -m src.kg.resolve run \
  --input experiments/kg/full_v21_extraction.jsonl --prefix er_full
```

4. Load mentions and entities into Neo4j:

```bash
python -m src.kg.load_neo4j --scope full --run-id full_v21 \
  --extraction experiments/kg/full_v21_extraction.jsonl \
  --resolution experiments/kg/er_full_mentions.jsonl
```

5. Check the result:

```bash
python -m src.kg.stats --scope full
python -m src.kg.coverage --scope full
```

Expected: 14,731 entities and 13,277 entity relations (the exact numbers change if the extraction is not served from the cache).

The pilot experiments (open extraction, prompt comparison, annotation) have their own commands; see the docstrings of `src/kg/extract.py`, `src/kg/annotation.py` and `src/kg/compare_prompts.py`.

---

## Retrieval over the graph

This needs the full graph in Neo4j and the Step 4 results (the rewrites and reranker scores are read from the cache).

1. Export entities and relations from Neo4j:

```bash
python -m src.kg_rag.graph_index --scope full
```

2. Evaluate entity linking:

```bash
python -m src.kg_rag.eval_linking
```

3. Run the graph pipelines (A-E and the random control) and evaluate them:

```bash
python -m src.kg_rag.run_qa --workers 12
python -m src.kg_rag.eval_qa
```

Expected token F1: ~24.5 for A, ~29.2 for E.

---

## Tests

```bash
python -m pytest tests
```

152 tests pass and 4 are expected failures that document open extraction issues. The tests in `tests/test_kg_build.py` need Neo4j and are skipped if it is not running.
