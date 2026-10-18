# Conversational RAG and Knowledge Graphs

A conversational question-answering system over the [MultiDoc2Dial](https://doc2dial.github.io/multidoc2dial/) documents (US government services: DMV, SSA, VA, StudentAid). It answers each user turn from retrieved passages and from facts of a knowledge graph built from the same documents, and abstains when the documents do not contain the answer. Research project in the [Master Degree in Computer Engineering](https://degrees.dei.unipd.it/master-degrees/computer-engineering/), [University of Padua](https://www.unipd.it/en/); supervisor Prof. Gianmaria Silvello.

Author: Danil Smirnov - danil.smirnov@studenti.unipd.it

## Architecture

```text
dialogue history + user turn
        |
  query rewriter ............ src/rag/query_rewriter.py   (LLM, self-contained search query)
        |
  passage retriever ......... src/rag/                    (BM25 + bge-small dense, fused by RRF, top 50)
        |
  reranker .................. src/rag/reranker.py         (bge-reranker-base cross-encoder, top 5)
        |
  knowledge graph ........... src/kg/                     (extraction with a closed schema, entity resolution, Neo4j)
    entity linking, facts ... src/kg_rag/                 (link the query to entities, rank their 1-hop facts)
        |
  generator ................. src/llm/, experiments/      (passages + facts in one prompt, dialogue history, abstention)
        |
      answer
```

All LLM calls (rewriting, extraction, entity resolution, generation) go to one Azure OpenAI deployment of `gpt-5.4-nano`. Data loading is in `src/data`, metrics and the LLM judge in `src/evaluation`.

## Configurations evaluated

All use the same generator and prompt; they differ in what the context contains.

* **LLM only**: no context.
* **Passages**: the top 5 sections from the rewriter, retriever and reranker.
* **Graph sections**: the sections reached through the linked entities.
* **Graph facts**: up to 30 facts of the linked entities, each with an evidence quote.
* **Passages + graph facts**: the top 5 sections plus the graph facts in a separate block.
* **Passages + random facts** (control): the same number of random facts from the same domain.
* **Oracle**: the gold sections of the question.

## Results

Token F1 (%), all questions / answerable questions only. Validation: 4,427 questions; test: 4,335, run once with the frozen systems.

| Configuration | Validation | Test |
| :--- | :---: | :---: |
| LLM only | 15.8 / 15.7 | 15.1 / 15.0 |
| Passages | 26.9 / 27.2 | 26.9 / 27.1 |
| Graph sections | 23.0 / 22.4 | - |
| Graph facts | 24.1 / 23.8 | 23.8 / 23.3 |
| Passages + graph facts | 27.4 / 27.7 | **27.5 / 28.0** |
| Passages + random facts | 27.4 / 27.2 | 27.3 / 27.1 |
| Oracle | 35.5 / 36.5 | 34.2 / 35.1 |

The graph alone is worse than passage retrieval; its facts added to the passages give a small, significant gain on answerable questions that random facts do not give. Giving the generator the dialogue history, with the abstention decision taken without it, raises validation F1 to 27.5 (passages) and 28.0 (passages + graph facts).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the values
```

Variables in `.env`: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_BASE_URL`, `LLM_MODEL` (generator); `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (graph); `HF_TOKEN`, `JUDGE_MODEL` (LLM judge, optional); `AZURE_FOUNDRY_ENDPOINT`, `AZURE_FOUNDRY_KEY`, `AZURE_FOUNDRY_DEPLOYMENT` (second generator, optional).

Put MultiDoc2Dial v1.0 into `data/multidoc2dial/`. The passage index (BM25 and dense embeddings, cached in `data/cache/`) is built on the first run of any pipeline.

```bash
# passage pipelines on the 500-question development subset
python experiments/run_dev_subset.py --workers 12 --pipelines llm oracle_v2 rewrite_v2 rewrite_rerank_v2

# knowledge graph (Neo4j in Docker)
docker compose up -d neo4j
python -m src.kg.structure
python -m src.kg.extract_closed --all --prompt-version v2.1 --output experiments/kg/full_v21_extraction.jsonl
python -m src.kg.resolve run --input experiments/kg/full_v21_extraction.jsonl --prefix er_full
python -m src.kg.load_neo4j --scope full --run-id full_v21 \
  --extraction experiments/kg/full_v21_extraction.jsonl --resolution experiments/kg/er_full_mentions.jsonl
python -m src.kg_rag.graph_index --scope full

# evaluation on a full split (validation or test)
python experiments/run_split.py --split validation --workers 12
python -m src.kg_rag.run_qa --split validation --workers 12
python -m src.kg_rag.eval_qa --split validation
python -m pytest tests
```

LLM answers are cached in `experiments/cache/`, so reruns are free. The full list of commands is in [docs/experiment_log.md](docs/experiment_log.md).

## Repository map

* `src/`: the system (`data`, `llm`, `rag`, `kg`, `kg_rag`, `evaluation`).
* `experiments/`: run and evaluation scripts, result summaries (`results/`) and the reports of the graph work (`kg/`, `kg_rag/`).
* `docs/`: the schematic report and the experiment log.
* `latex_report/`: the full report (unipd-thesis-modern template).
* `tests/`: unit and regression tests.
* `data/`: the dataset (not tracked), the development subset ids and the index cache.

Raw outputs (`*.jsonl`) and LLM caches are not tracked.

## Reports and documentation

* [Schematic report](docs/schematic_report.pdf): one short answer per question, with diagrams.
* [Full report](latex_report/main.pdf), source in [latex_report/](latex_report/).
* [Evaluation report](experiments/final_evaluation_report.md): full validation and test split.
* [Experiment log](docs/experiment_log.md): the work in the order it was done, with intermediate results and the old step names.
