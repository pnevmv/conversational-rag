# Building the knowledge graph

How to build the graph used by the graph configurations, from the MultiDoc2Dial documents to the files read by the retrieval code. The extraction and entity-resolution calls are cached, so a rebuild on the same machine is free. Back to the [README](../README.md).

## Neo4j and the full graph

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

## Retrieval over the graph

This needs the full graph in Neo4j and the results of the passage pipeline (`experiments/run_split.py`), whose rewrites and reranker scores are read from the cache.

1. Export entities and relations from Neo4j:

```bash
python -m src.kg_rag.graph_index --scope full
```

2. Evaluate entity linking:

```bash
python -m src.kg_rag.eval_linking
```

3. Run the graph configurations (graph sections, graph facts, passages + graph facts and the random control; the old names A, B and E) and evaluate them on the 500-question development subset, or add `--split validation` / `--split test`:

```bash
python -m src.kg_rag.run_qa --workers 12
python -m src.kg_rag.eval_qa
```

Expected token F1 on the development subset: ~24.5 for graph sections, ~29.2 for passages + graph facts.
