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

## How the answer is generated

G0 (abstention check, whole) and G2 (the answer, streamed) are started at the same time. The decision is unchanged: if G0 abstains the answer is "Unfortunately, no relevant information is found." and the G2 text is dropped, otherwise the answer is the G2 text. The prompts and the final answer are the same as in the sequential version (`check_replay.py` checks the prompts).

* **On screen:** the G2 text is shown while it is written, with the citation brackets removed on the fly (an unclosed `[` is held back). If G0 abstains, the text is replaced by the abstention. At the end the chat shows the final text, the sources and the cost, identical to the non-streamed answer.
* **Cost:** G2 is always called, also when G0 abstains, so a refused turn costs one generator call more than a sequential run would, and the turn waits for it (its tokens are listed as `G2 (discarded)`). A call of G2 cannot reuse the prompt cache that G0 fills, so the cost per turn is a few percent higher.
* **Times:** the Time line shows `G0+G2` as one step and, from the moment Send was pressed, the **first token** and, with voice, the **first audio** and when the last audio arrived (**voice done**).

A turn takes about 7–11 s on a laptop (rewrite about 1–2.5 s, passage reranking about 2.5 s, V1 fact scoring about 1 s, G0 and G2 together 1.5–3 s) and costs about USD 0.0006–0.002.

## Voice (ElevenLabs, experiment)

Each answer can be read aloud with ElevenLabs text to speech (`demo/tts.py`, official `elevenlabs` SDK, pinned in `demo/requirements.txt`). The audio is made sentence by sentence while the model is still writing: a sentence goes to ElevenLabs as soon as the next one has started, one request at a time, and the audio chunks are played in order.

1. `pip install -r demo/requirements.txt`, then put `ELEVENLABS_API_KEY` in `.env` (optionally `ELEVENLABS_VOICE_ID` and `ELEVENLABS_MODEL`, see `.env.example`). Without the key the **Voice** checkbox is off and the demo works as before.
2. Start the demo as usual. With **Voice** checked, the text streams in and the audio starts playing automatically after the first sentence.

* **Voice model:** `eleven_flash_v2_5` (default, lowest latency), `eleven_turbo_v2_5`, `eleven_multilingual_v2` or `eleven_v3` (more natural, slower, more credits per character).
* **When the voice starts:** the G2 text appears at once, but the voice starts only after G0 has finished without abstaining; sentences written before that wait. After an abstention nothing from the streamed text is read; the abstention sentence is read at the end, like any answer.
* **What is read:** the final answer without citation brackets, markdown or URLs; the source line is not read.
* **Sentences:** split at `.`, `!`, `?` followed by a capital letter, not after abbreviations such as U.S., e.g. or Dr.; fragments under 20 characters are merged into the neighbour and chunks over 400 characters are cut at `;` or `,`. The previous sentence is sent as `previous_text` to keep the intonation continuous (`next_text` is not known while the text is written); a model that rejects it (e.g. `eleven_v3`) is called without it.
* **First audio:** seconds from the moment Send was pressed to the first synthesized sentence, so it includes the retrieval steps and the time the model needs to write the first sentence. Answers are short (usually one to three sentences), so the voice starts shortly before the text is complete.
* **Cost and files:** the line under the player shows the model, the characters, the credits ElevenLabs reports (header `character-cost`), the sentences and the first audio time. Each answer is logged to `demo/logs/tts_usage.jsonl`; the whole answer is saved as one mp3 in `demo/logs/tts/` (both ignored by git) and can be downloaded with the button next to the line.
* A voice error (bad key, no credits, network) is shown under the player and does not affect the text answer; sentences played before the error stay played.

## Differences from the evaluation

* **History:** in the evaluation the history in the prompts held the gold agent turns of the dataset; here it holds the system's own earlier answers (without citations), so a wrong answer can carry over to later turns. The rewriter sees the last 6 turns and the generator the whole history, as in the evaluation.
* **Citations:** the citation prompt was evaluated for E only (validation F1; judge score on dev-500 67.7 against 68.1 without citations). For P its instruction does not mention facts; for V1 it is the E instruction unchanged, which says facts are numbered up to [F30] although V1 gives 10.
* **No caches:** every turn calls the model; nothing is written under `experiments/`. Token usage is logged to `demo/logs/usage.jsonl` (ignored by git).

## Check

```bash
python demo/check_replay.py
```

Builds the contexts and G0/G2 prompts of 20 validation questions with the stored rewrites and the gold history, and compares them with the stored results of P, E, V1 and E with citations (no LLM calls).
