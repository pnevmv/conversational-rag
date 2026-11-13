# Demo chat

A local chat with the final system: LLM query rewriting, hybrid passage retrieval (BM25 + bge-small, RRF top 50), cross-encoder reranking (bge-reranker-base, top 5), graph facts, and gpt-5.4-nano answering with G2 + abstain(G0). It reuses the experiment code; `check_replay.py` confirms that it builds the same contexts and prompts as the evaluated systems.

## Start

1. Install the demo dependency into the project environment: `pip install -r demo/requirements.txt` (Gradio 6.30.0, tested with Python 3.14).
2. Put the Azure OpenAI settings in `.env` at the project root (`AZURE_OPENAI_API_KEY`, and optionally `AZURE_OPENAI_BASE_URL`, `LLM_MODEL`), as for the experiments. The keys are read from there only and are never printed or logged.
3. Run:

```bash
python demo/app.py                                  # http://127.0.0.1:7860
python demo/app.py --share --auth user:password     # temporary public link (72 h); --auth is required
```

Neo4j does not need to be running: the graph is served from the JSON exports in `experiments/kg_rag/`, which were made from Neo4j. Loading the indexes, the models and the graph takes a few seconds at startup; the data files of the experiments (`data/`, `experiments/kg_rag/`) must be present.

## What the page shows

* **System:** P (passages), E (passages + 30 one-hop graph facts, the default) or V1 (passages + the top 10 facts by cross-encoder score).
* **Citations:** on by default (the citation prompt was tested on E only). The answer prompt asks the model to cite the passages ([2]) and facts ([F7]) it used; the cited sections are listed under the answer and the brackets are removed from the answer text. Unchecked, the demo is exactly the evaluated system, and the source shown is the passage or fact section that shares the most words with the answer.
* **Side panels:** the rewritten query, the top 5 passages with their reranker scores, the graph facts in the prompt (head —relation→ tail, with the evidence quote), and the tokens (input, cached input, output) and cost of this turn and of the conversation, with the time of each step. Cached input tokens are the start of a prompt that the API reuses from an earlier call; they are billed at a tenth of the input price, so the cost is not proportional to the input tokens.
* **New conversation** clears the history and the totals.

A turn takes about 7–11 s on a laptop (rewrite about 1–2.5 s, passage reranking about 2.5 s, V1 fact scoring about 1 s, two generator calls of 1.5–3 s each) and costs about USD 0.0006–0.002.

## Differences from the evaluation

* **History:** in the evaluation the history in the prompts held the gold agent turns of the dataset; here it holds the system's own earlier answers (without citations), so a wrong answer can carry over to later turns. The rewriter sees the last 6 turns and the generator the whole history, as in the evaluation.
* **Citations:** the citation prompt was evaluated for E only (validation F1; judge score on dev-500 67.7 against 68.1 without citations). For P its instruction does not mention facts; for V1 it is the E instruction unchanged, which says facts are numbered up to [F30] although V1 gives 10.
* **No caches:** every turn calls the model; nothing is written under `experiments/`. Token usage is logged to `demo/logs/usage.jsonl` (ignored by git).

## Check

```bash
python demo/check_replay.py
```

Builds the contexts and G0/G2 prompts of 20 validation questions with the stored rewrites and the gold history, and compares them with the stored results of P, E, V1 and E with citations (no LLM calls).
