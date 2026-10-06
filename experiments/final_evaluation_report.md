# Final evaluation: full validation split and test split

All earlier comparisons were made on dev-500, a fixed 500-question subset of the validation split, and several design choices were taken by looking at it. To get results that were not used for any decision, the work was finished in two more steps:

1. the systems whose choice was still open were run on the full validation split (4,427 questions), the remaining decisions were taken there, and the final systems were frozen;
2. the frozen systems were run once on the test split (4,335 questions, 241 unanswerable), which had never been used before. Nothing was changed after looking at the test results.

Everything uses the same generator (`gpt-5.4-nano`), the agent-style prompt with its few-shot examples, the cached query rewrites and the same evaluator as dev-500. To reproduce:

```bash
python experiments/run_split.py --split validation --workers 12
python experiments/run_split.py --split test --workers 12 --systems llm_baseline oracle_context_v2 \
    rag_rewrite_rerank_v2 kg_facts step4_plus_facts step4_plus_random_facts
python experiments/evaluate_diagnostics.py --inputs experiments/results/<split>/*.jsonl ...
python -m src.kg_rag.eval_qa --split validation      # or --split test
```

Summaries are in `experiments/results/validation/` and `experiments/results/test/` (`diagnostics.md`, `kg_qa_summary.json`); the per-question answers are not tracked.

## 1. Decisions on the full validation split

Token F1 and ΔF1 against the Step 4 best pipeline (hybrid retrieval + rewriting + reranking, agent prompt), paired bootstrap with 95% intervals:

| System | R@5 | F1 | ΔF1, all | ΔF1, answerable | Abstain recall / false abstention |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Step 4 best | 63.7 | 26.9 | - | - | 19.5 / 4.5 |
| without the reranker | 59.8 | 26.5 | -0.3 [-0.8, 0.1] | -0.3 [-0.7, 0.0] | 19.5 / 4.5 |
| with the old prompt | 63.7 | 27.3 | +0.4 [-0.0, 0.8] | -0.4 [-0.7, -0.1] | 36.0 / 6.0 |
| A: graph -> sections | 34.0 | 23.0 | -3.9 [-4.5, -3.4] | | 32.3 / 10.4 |
| B: graph facts only | 36.6 | 24.1 | -2.7 [-3.3, -2.1] | -3.4 [-3.9, -3.0] | 30.1 / 7.6 |
| E: Step 4 sections + graph facts | 63.7 | 27.4 | +0.5 [0.1, 0.9] | +0.5 [0.2, 0.8] | 19.0 / 3.4 |
| E-random (control) | 63.7 | 27.4 | +0.6 [0.2, 1.0] | -0.0 [-0.3, 0.2] | 31.4 / 5.6 |

LLM only reaches 15.8 and the oracle (gold sections given directly) 35.5.

The open questions were settled as follows:

* The reranker is kept. It raises Recall@5 by 3.9 points; the F1 difference is small and not significant, but not negative.
* The agent-style prompt is kept. The old prompt is 0.4 points better overall only because it abstains much more often (abstain recall 36% against 20%), which is rewarded on the 226 unanswerable questions; on answerable questions it is 0.4 points worse, and it gives more false abstentions. It also triggered 7 content-filter errors.
* B stays the better graph-only option (facts rather than sections), and both are clearly worse than passage retrieval.
* E is kept as the combination of graph and passages, with E-random as its control: on answerable questions E gains +0.5 and random facts gain nothing, and E beats random facts by 0.6 [0.2, 0.9].

The frozen systems for the test split were LLM only, the oracle, the Step 4 best pipeline, B, E and E-random.

## 2. Test split

| System | R@5 | F1 [95% CI] | F1 on hits / misses | Abstain recall | False abstention |
| :--- | :---: | :---: | :---: | :---: | :---: |
| LLM only | - | 15.1 [14.7, 15.5] | - | 14.5 | 11.8 |
| Oracle | 100 | 34.2 [33.6, 34.9] | 35.1 / - | 18.7 | 2.4 |
| Step 4 best | 66.6 | 26.9 [26.3, 27.5] | 31.9 / 17.4 | 22.4 | 5.2 |
| B: graph facts only | 38.7 | 23.8 [23.2, 24.4] | 28.6 / 19.9 | 32.0 | 10.0 |
| E: Step 4 sections + graph facts | 66.6 | 27.5 [27.0, 28.2] | 32.4 / 19.0 | 19.1 | 3.3 |
| E-random | 66.6 | 27.3 [26.7, 27.9] | 31.8 / 17.6 | 29.9 | 6.5 |

ΔF1 against the Step 4 best pipeline:

| | All | Answerable | Step 4 misses the gold section | Unanswerable |
| :--- | :---: | :---: | :---: | :---: |
| B | -3.1 [-3.7, -2.5] | -3.8 [-4.3, -3.3] | +1.0 [0.4, 1.8] | +9.2 [2.5, 15.5] |
| E | +0.6 [0.2, 1.1] | +0.8 [0.5, 1.2] | +1.6 [1.1, 2.1] | -2.9 [-8.1, 2.2] |
| E-random | +0.4 [-0.0, 0.8] | -0.0 [-0.3, 0.3] | +0.2 [-0.1, 0.6] | +7.6 [2.0, 13.0] |
| E vs E-random | +0.2 [-0.2, 0.7] | +0.9 [0.6, 1.2] | +1.4 [0.9, 1.9] | |

On the 2,206 answerable test questions where at least one of E's facts comes from the gold section, E gains +1.4 [1.0, 1.8] over the Step 4 best pipeline; on the others it gains +0.2 [-0.2, 0.6].

## 3. What holds

The test results reproduce the validation results almost exactly, and both agree with dev-500:

* LLM only (15) < graph-only retrieval (24) < passage RAG (27) < passages + graph facts (27.5) < oracle (34).
* Retrieval over the graph alone is about 3 F1 points worse than passage retrieval, on every split.
* Graph facts added to the retrieved passages give a small but real gain: +0.6 overall and +0.8 on answerable questions, significant on both validation and test. On dev-500 the same effect (+0.9 on answerable questions) was only borderline.
* The random-facts control shows that the gain comes from the content of the facts: on answerable questions random facts gain nothing, and the graph facts beat them by 0.6 (validation) and 0.9 (test) points. The gain is concentrated where the facts come from the gold section and where passage retrieval misses it.
* Random facts look as good as real ones overall only because they make the model abstain more often, which pays on unanswerable questions. Overall F1 alone would therefore be misleading; answerable and unanswerable questions have to be reported separately.
* The gap between the best pipeline and the oracle stays at about 7 points, mostly from retrieval misses (on test, a gold section is in the top 5 for 67% of the answerable questions, and F1 is 31.9 on those against 17.4 on the others).

## 4. Notes on the runs

* Azure's content filter blocked 8 of about 66,000 generated answers (7 in the old-prompt variant on validation, 1 in LLM only on test); those questions are left out of the scores of these two systems.
* During the test run a race condition was found: when two questions produced exactly the same rewrite prompt, both were sent to the model at the same time and could get different rewrites, while only one was cached. It affected 7 test questions in the retrieval cache used by the graph pipelines, and was caught by a check that the sections part of E equals the Step 4 context. The parallel runner now sends identical prompts only once, the cache was rebuilt and the graph pipelines were rerun; the systems already finished were not affected. Validation and dev-500 passed the same check.
* Reranking 4,427 x 50 pairs on the laptop GPU took about 90 minutes once the reranker released GPU memory between chunks (before that, memory grew until the system swapped). Scores are cached per chunk, so an interrupted run resumes.
