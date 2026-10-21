# Conversational RAG and Knowledge Graphs

A conversational question-answering system over the [MultiDoc2Dial](https://doc2dial.github.io/multidoc2dial/) documents (US government services: DMV, SSA, VA, StudentAid). It answers each user turn from retrieved passages and from facts of a knowledge graph built from the same documents, and abstains when the documents do not contain the answer. Research project in the [Master Degree in Computer Engineering](https://degrees.dei.unipd.it/master-degrees/computer-engineering/), [University of Padua](https://www.unipd.it/en/); supervisor Prof. Gianmaria Silvello.

Author: Danil Smirnov - danil.smirnov@studenti.unipd.it

## Key findings

* **The graph alone is worse than passages.** Graph sections reach 23.0 and graph facts 24.1 token F1 on validation, against 26.9 for passage retrieval (test: 23.8 vs 26.9 for graph facts).
* **Graph facts added to the passages give a small gain on answerable questions** (validation 27.7 vs 27.2, test 28.0 vs 27.1), which the same number of random facts does not give (27.2 and 27.1).
* **Giving the generator the dialogue history, with the abstention decision taken separately, gives the best result**: 28.0 overall and 28.2 on answerable questions with passages + graph facts (validation).

## Architecture

![Architecture: offline indexing and graph construction, online answering of a user turn](docs/figures/architecture.png)

| Component | Module |
| :--- | :--- |
| Sections, dataset loading | `src/data/` |
| Passage index, retriever (BM25 + bge-small, RRF), reranker (bge-reranker-base) | `src/rag/` |
| Query rewriter | `src/rag/query_rewriter.py` |
| LLM extraction, entity resolution, Neo4j loading | `src/kg/` |
| Entity linking, 1-hop fact retrieval | `src/kg_rag/` |
| LLM client, cache, per-call token usage log | `src/llm/` |
| Generator prompt, dialogue history, abstention decision | `experiments/run_dev_subset.py`, `experiments/generator_input.py` |
| Metrics | `src/evaluation/` |

All LLM calls (rewriting, extraction, entity resolution, generation) go to one Azure OpenAI deployment of `gpt-5.4-nano`.

## Configurations evaluated

All use the same generator and prompt; they differ in what the context contains.

* **LLM only**: no context.
* **Passages**: the top 5 sections from the rewriter, retriever and reranker.
* **Graph sections**: the sections reached through the linked entities.
* **Graph facts**: up to 30 facts of the linked entities, each with an evidence quote.
* **Passages + graph facts**: the top 5 sections plus the graph facts in a separate block.
* **Passages + random facts** (control): the same number of random facts from the same domain.
* **Oracle**: the gold sections of the question.
* **..., with dialogue history**: the generator also sees the whole dialogue so far; whether to abstain is decided by the prompt without history.

## Results

Token F1 (%), all questions / answerable questions only. Validation: 4,427 questions; test: 4,335, run once with the frozen systems.

| Configuration | Validation | Test |
| :--- | :---: | :---: |
| LLM only | 15.8 / 15.7 | 15.1 / 15.0 |
| Passages | 26.9 / 27.2 | 26.9 / 27.1 |
| Graph sections | 23.0 / 22.4 | not run |
| Graph facts | 24.1 / 23.8 | 23.8 / 23.3 |
| Passages + graph facts | 27.4 / 27.7 | 27.5 / 28.0 |
| Passages + random facts | 27.4 / 27.2 | 27.3 / 27.1 |
| Passages, with dialogue history | 27.5 / 27.6 | not run yet |
| Passages + graph facts, with dialogue history | **28.0 / 28.2** | not run yet |
| Oracle (upper bound) | 35.5 / 36.5 | 34.2 / 35.1 |

## Example

A follow-up turn of a validation dialogue (DMV, traffic tickets), answered by passages + graph facts:

| | |
| :--- | :--- |
| User | what if im a holder of a junior license? |
| Reference | you can not plead by mail or online. you still must appear for a hearing in a tvb office. |
| Answer | If you are a holder of a probationary/junior license or a learner permit, you cannot plead by mail or online. You must appear for a hearing in a TVB office. (F1 0.67; passages alone: 0.51) |
| Graph fact | `probationary / junior license or learner permit (Role) exempt from plead by mail or online (Service)`, evidence: "you cannot plead by mail or online" (Traffic Violations Bureau, APPEALS) |

The relation name is not right (these drivers cannot plead by mail), but the evidence quote is, which is why every fact is given to the model with its quote.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in the values; each variable is explained in .env.example
```

Put MultiDoc2Dial v1.0 into `data/multidoc2dial/`. The graph configurations also need the knowledge graph, see [docs/graph_build.md](docs/graph_build.md). LLM answers are cached in `experiments/cache/`, so with an existing cache the commands below make no new calls. To reproduce the validation column of the results table:

```bash
python experiments/run_split.py --split validation --workers 12                      # LLM only, oracle, passages
python -m src.kg_rag.run_qa --split validation --workers 12                          # graph configurations
python -m src.kg_rag.eval_qa --split validation                                     # F1 of passages and graph configurations
python experiments/generator_input.py --split validation --k all                     # with dialogue history
```

LLM only and the oracle are scored with `python experiments/evaluate_diagnostics.py --inputs experiments/results/validation/*.jsonl`. The test column uses `run_split.py`, `run_qa` and `eval_qa` with `--split test`. The full list of commands is in [docs/experiment_log.md](docs/experiment_log.md).

## Repository map

* `src/`: the system (`data`, `llm`, `rag`, `kg`, `kg_rag`, `evaluation`).
* `experiments/`: run and evaluation scripts, result summaries (`results/`) and the reports of the graph work (`kg/`, `kg_rag/`).
* `docs/`: the schematic report, the experiment log, the graph build guide and the figures.
* `latex_report/`: the full report (unipd-thesis-modern template).
* `tests/`: unit and regression tests (`python -m pytest tests`).
* `data/`: the dataset (not tracked), the development subset ids and the index cache.

Raw outputs (`*.jsonl`) and LLM caches are not tracked.

## Reports and documentation

* [Schematic report](docs/schematic_report.pdf): one short answer per question, with diagrams.
* [Full report](latex_report/main.pdf), source in [latex_report/](latex_report/).
* [Evaluation report](experiments/final_evaluation_report.md): full validation and test split.
* [Experiment log](docs/experiment_log.md): the work in the order it was done, with intermediate results and the old step names.
* [Graph build](docs/graph_build.md): Neo4j setup and the commands to build the knowledge graph.
