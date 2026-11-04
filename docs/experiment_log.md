# Experiment log

This file keeps the history of the work in the order it was done, with the intermediate results. The work was planned in numbered steps for the supervisor; the code, result files and older reports still use those names. The table maps them to the component and configuration names used in the README.

| Old name (reports, result files) | Component or configuration |
| :--- | :--- |
| Step 3, LLM-only baseline (`llm_baseline`) | configuration *LLM only* |
| Oracle (`oracle_context_v2`) | configuration *oracle* (gold sections given to the generator) |
| Step 4, RAG | query rewriter, passage retriever and reranker (`src/rag`) |
| Step 4 best: hybrid + rewrite + rerank (`rag_rewrite_rerank_v2`) | configuration *passages* |
| Step 5, knowledge graph construction | graph extraction and entity resolution (`src/kg`) |
| Step 6, retrieval over the graph | entity linking and fact retrieval (`src/kg_rag`) |
| Step 6 A (`kg_sections`) | configuration *graph sections* |
| Step 6 A with 1-hop (`kg_sections_1hop`) | graph sections with 1-hop expansion (dev-500 only) |
| Step 6 B (`kg_facts`) | configuration *graph facts* |
| Step 6 C (`kg_hybrid`) | graph and passage rankings fused before the reranker (dev-500 only, dropped) |
| Step 6 D (`kg_rerank`) | graph candidates reranked (dev-500 only, dropped) |
| Step 6 E (`step4_plus_facts`) | configuration *passages + graph facts* |
| Step 6 E-random (`step4_plus_random_facts`) | configuration *passages + random facts* (control) |
| G0 / G1 / G2 / G3 (`generator_input/`) | generator with the user turn / the rewritten query / the dialogue history / both |
| G2 + abstain(G0) | generator with dialogue history, abstention decided by the G0 prompt |
| Agents (`src/agents`, `experiments/agent.py`) | sufficiency check with one extra round (A1) and tool-calling agent (A2); negative result |

## Earlier README

The text below is the README as it was before the restructuring, unchanged except for the heading levels.

### Project description

This repository contains the code, experiments and write-up of a research project on conversational question answering over document collections, starting from Retrieval-Augmented Generation (RAG) and moving towards Knowledge Graphs (KGs), Graph RAG and agent-based approaches.

The work is carried out within the

* [Master Degree in Computer Engineering](https://degrees.dei.unipd.it/master-degrees/computer-engineering/) of the [Department of Information Engineering](https://www.dei.unipd.it/en/), [University of Padua](https://www.unipd.it/en/), Italy.

Supervisor: Prof. Gianmaria Silvello.

The main benchmark is [MultiDoc2Dial](https://doc2dial.github.io/multidoc2dial/), a dataset of goal-oriented dialogues grounded in government-service documents from four domains (DMV, SSA, VA, StudentAid). EnronQA and MTRAG are kept as secondary datasets. The methodology follows *Knowledge Graphs and LLMs in Action* (Negro et al., Manning), mostly Parts 1, 3, 5 and 6.

### Author
- Danil Smirnov - danil.smirnov@studenti.unipd.it

### Organisation of the repository

The repository is organised as follows:

* `src`: the source code. `llm` is the Azure OpenAI client with a parallel runner and a disk cache, `data` the MultiDoc2Dial loader, `evaluation` the metrics, `rag` the retrievers, query rewriter and reranker, `kg` the knowledge graph construction (schema, extraction, entity resolution, Neo4j loaders) and `kg_rag` the retrieval over the graph.
* `experiments`: the scripts that run the pipelines and evaluate them, plus the reports of the KG work in `experiments/kg` and `experiments/kg_rag`.
* `latex_report`: the written report of the research (LuaLaTeX, unipd-thesis-modern template).
* `tests`: unit and regression tests.
* `data`: the dataset (not tracked), the ids of the fixed dev-500 subset and the dense index cache.

Raw model outputs (`*.jsonl`) and LLM caches are not tracked; they can be regenerated with the scripts below.

### Current status

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
| 9 | Evaluation and comparison | in progress (full validation and test done) |
| 10 | Error analysis and write-up | planned |

All LLM calls use an Azure OpenAI deployment of `gpt-5.4-nano`; set the deployment name in `LLM_MODEL`.

#### Steps 3-4: LLM baseline and RAG

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

#### Step 5: Knowledge graph construction

The graph is stored in Neo4j in three layers: a structural layer (domain, document, section, span), a metagraph with the mentions extracted by the LLM, and an entity layer obtained by entity resolution. Extraction uses a closed schema with 9 entity types and 11 relation types, designed after a small open-extraction pilot.

A few things learned on the way:

* extraction is not deterministic: two runs with the same settings share only 44-48% of their triples;
* on a pilot annotation of 3 documents, one run with the first prompt has 51% precision and 66% recall (76% precision for the triples two runs agree on); the second prompt was not more precise (46%) and found far fewer facts (recall 38%);
* embedding similarity is not enough to merge entities (about half of the pairs above cosine 0.95 are different entities), so merges go through rules or a batched LLM judge, with a guard against generic "hub" names.

| Full graph (prompt v2.1) | |
| :--- | :--- |
| Entities | 14,731 (from 28,782 mentions) |
| Entity relations | 13,277 |
| dev-500 gold sections with an entity | 96.6% |
| Precision on a control sample (30 triples, unseen documents) | 73% [56, 86] |
| Cost | 12,970 LLM calls, about 1 hour |

All annotations were made by hand, without automatic help (`experiments/kg/reannotation/`). They replace a first round of labels that were drafted by an LLM and then reviewed; with those, the graph looked less precise (53% on the control sample) and the second prompt looked better than the first. Details are in `latex_report/chapters/kg_construction.tex` and `experiments/kg/full_build_report.md`.

#### Step 6: Retrieval over the knowledge graph

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

Retrieval over the graph alone is worse than passage retrieval: linking works, but entity overlap cannot rank the many sections the entities point to. Adding graph facts to the Step 4 context (E) gives a small gain on dev-500, but random facts from the same domain give the same overall number, mostly because the extra context makes the model abstain more. On answerable questions the real facts do help, and the final evaluation below confirms it. Reports: `experiments/kg_rag/phase1_report.md` and `experiments/kg_rag/phase2_report.md`.

#### Final evaluation: full validation and test split

The choices made on dev-500 were checked on the full validation split (4,427 questions), where the remaining open questions were settled: the reranker and the agent-style prompt are kept, B is the better graph-only option, and E is kept with its random-facts control. These six systems were then frozen and run once on the test split (4,335 questions), which had not been used for anything before.

| System (token F1) | Validation | Test |
| :--- | :---: | :---: |
| LLM only | 15.8 | 15.1 [14.7, 15.5] |
| Oracle (gold sections) | 35.5 | 34.2 [33.6, 34.9] |
| Step 4 best (hybrid + rewrite + rerank) | 26.9 | 26.9 [26.3, 27.5] |
| B: graph facts only | 24.1 | 23.8 [23.2, 24.4] |
| E: Step 4 sections + graph facts | 27.4 | **27.5** [27.0, 28.2] |
| E with random facts (control) | 27.4 | 27.3 [26.7, 27.9] |

On the test split, graph-only retrieval is 3.1 points below passage retrieval. Graph facts added to the passages gain +0.6 overall and +0.8 on answerable questions (both significant), and +1.4 where the facts come from the gold section. Random facts gain nothing on answerable questions; their overall number only holds up because they make the model abstain more. The validation split gives the same picture, so the small effect that was borderline on dev-500 is confirmed. Details: `experiments/final_evaluation_report.md` and `latex_report/chapters/final_evaluation.tex`.

---

### Running a whole split

The main systems can also be run on the full validation split or on the test split (about 3 hours for validation on a laptop, most of it reranking; progress is printed with timestamps and the reranker scores are cached per chunk, so an interrupted run resumes):

```bash
python experiments/run_split.py --split validation --workers 12
python experiments/run_split.py --split test --workers 12 --systems llm_baseline oracle_context_v2 \
    rag_rewrite_rerank_v2 kg_facts step4_plus_facts step4_plus_random_facts
python -m src.kg_rag.eval_qa --split test
```

Results go to `experiments/results/<split>/`.

---

### Quickstart - RAG on dev-500

You need Python 3 (developed with 3.14) and access to an Azure OpenAI deployment.

#### 1. Set up the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. Download the data

Download MultiDoc2Dial v1.0 from the [project page](https://doc2dial.github.io/multidoc2dial/) and unpack it into `data/multidoc2dial/`, so that the folder contains:

```text
data/multidoc2dial/multidoc2dial_doc.json
data/multidoc2dial/multidoc2dial_dial_train.json
data/multidoc2dial/multidoc2dial_dial_validation.json
data/multidoc2dial/multidoc2dial_dial_test.json
```

The ids of the dev-500 subset are already in `data/dev_500_ids.json`.

#### 3. Configure

```bash
cp .env.example .env
```

Then set in `.env`:

```env
AZURE_OPENAI_API_KEY=<your key>
AZURE_OPENAI_BASE_URL=https://<your resource>.services.ai.azure.com/openai/v1
LLM_MODEL=gpt-5.4-nano
```

#### 4. Run the pipelines

```bash
python experiments/run_dev_subset.py --workers 12 \
  --pipelines llm oracle_v2 rewrite_v2 rewrite_rerank_v2
```

The first run downloads bge-small and builds the dense index in `data/cache/` (about half a minute). LLM answers are cached in `experiments/cache/`, so re-runs are free. Results are written to `experiments/results/dev_500/`.

#### 5. Evaluate

```bash
python experiments/evaluate_diagnostics.py \
  --inputs experiments/results/dev_500/*.jsonl
```

Expected token F1 for `rag_rewrite_rerank_v2`: ~28.0.

The single pipelines on the full validation split can be run with `experiments/llm_baseline.py`, `experiments/rag_baseline.py`, `experiments/rag_dense_baseline.py`, `experiments/rag_hybrid_baseline.py`, `experiments/rag_rewrite_baseline.py` and `experiments/oracle_context.py`.

---

### Knowledge graph

#### Neo4j

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

#### Building the full graph

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

### Retrieval over the graph

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

### LLM judge

Token F1 only counts word overlap with the reference, so correct paraphrases get low scores. `experiments/judge_answers.py` re-scores the cached answers of the systems on dev-500 with an LLM judge, gpt-6-luna on the Azure Foundry endpoint (`AZURE_LUNA_*` in `.env`). A first version called Llama-3.3-70B through the Hugging Face router; it stopped after 10 answers per pipeline when the credits ran out. The judge sees the last four turns of the dialogue, the question, the reference answer, the gold section and the context the model was given (up to 24,000 characters, enough for 5 passages and 30 facts). It rates each answer as correct, partial or incorrect, and separately says whether the answer is supported by the section or the context. Abstentions are scored by rule (correct only on unanswerable turns), without a call. Citations are stripped before judging. The agents' extended contexts are not stored, so for them "supported" is judged against the gold section only.

Systems: no documents, gold section given, P, E, E with citations, V1, and the agents A1 and A2 (with abstain(G0) and with their own refusal). Score differences are paired against E.

1. Count the tokens and estimate the cost (no API calls; cached calls are not counted):

```bash
python experiments/judge_answers.py cost
```

2. Try it on a few answers, then run all systems (about 3,600 calls, 6.4M input tokens; cached, so reruns are free):

```bash
python experiments/judge_answers.py run --limit 10
python experiments/judge_answers.py run --workers 8
```

The summary is written to `experiments/results/judge/gpt-6-luna/dev_500/summary.md`.

3. Check the judge against human labels on 60 answers of P, E and V1 (each distinct answer once, seed 42): 30 at random, 15 judged incorrect with the highest F1 and 15 judged correct with the lowest F1. The judge verdict and the system are kept in a separate key file. `agreement` reports Cohen's kappa for the three classes and for two binary splits (correct vs not, correct+partial vs incorrect), overall, on the random half and on the disagreement half. A second run of the judge (stability) is only planned if the human check is borderline.

```bash
python experiments/judge_answers.py export      # fill `label` in experiments/results/judge/gpt-6-luna/dev_500/human_labels.csv
python experiments/judge_answers.py carry --from labels.csv   # labels of an earlier sample, if the same answers were drawn again
python experiments/judge_answers.py agreement
```

Agreement with the human labels (`experiments/results/judge/gpt-6-luna/dev_500/human_agreement.json`): Cohen's kappa 0.65 for the three classes (random half 0.66, disagreement half 0.59), 0.69 for correct vs not and 0.75 for correct+partial vs incorrect. The judge is stricter than the human labels: in 9 of the 12 disagreements its verdict is lower.

4. Since kappa is at least 0.6, the final systems P, E and V1 are judged on the whole validation and test splits. This is evaluation only, no system is re-selected; the judge scores are reported next to F1:

```bash
python experiments/judge_answers.py run --split validation
python experiments/judge_answers.py run --split test
```

---

### Tests

```bash
python -m pytest tests
```

156 tests pass. Four more are marked as known issues of the model's extraction output (expected failures, e.g. a reversed relation in a fee table); they are kept so that a fix in a later prompt or model shows up. The tests in `tests/test_kg_build.py` need Neo4j and are skipped if it is not running.

## Generator input and abstention (after the final evaluation)

All results above give the generator only the current user turn and the retrieved context. Four generator inputs were then compared on the full validation split with retrieval unchanged (`experiments/generator_input.py`): G0 the user turn (as above), G1 the rewritten query, G2 the whole gold dialogue history plus the user turn (history length chosen on dev-500), G3 both. G2 gains on answerable questions (+0.8 F1 with passages, +0.7 with passages + graph facts) but abstains half as often; G1 and G3 are worse. Taking the abstention decision from G0 and the answer from G2 gives the best overall F1 (27.5 with passages, 28.0 with passages + graph facts). Two cheaper decisions, a yes/no classifier call and a threshold on the top reranker score (`experiments/abstention_decision.py`), both lose against it. Summaries: `experiments/results/validation/generator_input/` (`summary.md`, `abstention_decision.md`, `unanswerable_examples.md`).

## Agents: sufficiency check and tool use (negative result)

**Question.** In about 27% of the validation questions the gold section is not in the top 5, and F1 there is far lower. The graph facts rescue some of these (+4.6 F1 on 342 questions) but a router on pre-generation signals could not tell which ones, and the generator with the dialogue history refuses too rarely, which is why the refusal comes from G0. The agent experiments asked whether the model itself can judge from the retrieved context that it is not enough, and whether looking further repairs it.

**Plan and stopping rule (fixed before any run, 2026-10-29).** Baseline E with citations (passages + 30 facts, G2 + abstain(G0), gpt-5.4-nano), development on dev-500, decisions on the full validation split, the test split used once for a single frozen agent.
* *A1, fixed controller:* one check on (rewritten query, top-5 sections, facts) answering sufficient / insufficient plus what is missing; if insufficient, one extra round (new query, hybrid retrieval and reranking, facts of newly linked entities, new top 5 added to the old one), then answer or refuse. Refusal: abstain(G0) on the new context, with "refuse if a second check is still insufficient" as a paired alternative.
* *A2, tool-calling agent:* starts from E's context, tools `search_passages`, `get_entity_facts`, `answer`, `refuse`, at most 3 tool calls.
* *Keep* a variant only if Δ F1 on all questions against E has its interval above 0 (and answerable questions do not get significantly worse), or ties E (Δ ≥ −0.2) at least 10% cheaper; *drop* it if the interval on all or on answerable questions is entirely below 0. A2 was run only if the check of A1 was better than chance on dev-500 (Youden's J ≥ 0.2 with the lower bound above 0). Each run was estimated in calls and cost beforehand and capped at 1.5 times the estimate.

**A1 (dev-500, 500 questions).**
* The check works: against "gold section in context" (passages or facts, answerable questions) J = 0.33 [0.23, 0.42]; "sufficient" has precision 0.86 and recall 0.63, "insufficient" precision 0.39 (base rate of missing gold 25%) and recall 0.70. It says insufficient on 58% of the 31 unanswerable questions. The gate was passed.
* The extra round (46% of the questions) adds little: on the 213 answerable ones the new query alone puts a gold section in its top 5 less often than E's query (45.5% against 53.5%), and the union with E's top 5 raises passage recall only from 53.5% to 59.2% (+5.6 points); gold in the whole context goes from 61.0% to 65.7%.
* The larger context makes G0 abstain less (abstain recall 32.3% against 41.9% for E). Δ F1 against E: −0.6 on all questions [−1.6, +0.4], +0.1 on answerable ones [−0.5, +0.6], at USD 2.29 per 1,000 turns against 1.39 (+65%) and 2.9 model calls per turn against 1.9.
* Own refusal (refuse if the second check is still insufficient) is much worse: −6.6 on all questions [−8.5, −4.7], because the second check calls 80% of the round questions insufficient and false abstention reaches 37%.
* Decision: A1 cannot reach the keep condition at +65% cost, so it was not run on the full validation split.

**A2 (dev-500).**
* The agent used a tool on 44% of the questions (209 with one call, 11 with two, none at the limit; 220 searches, 11 fact lookups) and called `refuse()` 4 times. Tool use as a predictor of missing gold: J = 0.21 [0.12, 0.31].
* With abstain(G0): Δ −1.5 on all questions [−2.9, −0.1], −0.9 on answerable ones [−2.0, +0.1], USD 1.98 per 1,000 turns (+42%).
* With its own refusal: Δ −2.8 on all questions [−4.5, −1.3] but −0.5 on answerable ones [−1.6, +0.6], a tie, at USD 1.23 per 1,000 turns (−12%, one call replaces the G0 + G2 pair). The loss comes from the unanswerable questions: the agent almost never refuses (abstain recall 3.2% against 41.9%; 31 unanswerable questions, so noisy).
* Decision: both variants have the interval on all questions entirely below 0; A2 was dropped without a full-validation run.

**Exploratory check, not in the plan (no LLM calls).** On the 213 answerable questions A1 sent to the extra round, a gold section outside E's top 5 is at ranks 6-10 of E's own reranked list for 8.9% of them, against 5.6% brought in by the new query (12.7% together); for the 83 questions where the context really lacks the gold section, 14.5% against 9.6%. Chosen after seeing the A1 result, one dev-500 subset, no interval.

**Conclusion.** The model can tell when the context is missing the gold section (J 0.33), but neither a second search with its own query nor a tool-using agent recovers it often enough to pay off, and the extra context costs abstentions on unanswerable questions. An agent that decides to refuse on its own almost never refuses (abstain recall 3%), as with the dialogue history in G2; the refusal has to come from a separate decision such as G0. E stays the final system. Future work: add ranks 6-10 of the original list as the second round and combine it with a separate refusal decision; this idea comes from the exploratory check, so it needs a fresh validation run to mean anything.

Plan file: not in the repository. Code: `src/agents/`, `experiments/agent.py`. Results and decisions: `experiments/results/dev_500/agent/` (`decisions.md`, `a1_summary.json`, `a2_summary.json`, `a1_rank610.json`).
