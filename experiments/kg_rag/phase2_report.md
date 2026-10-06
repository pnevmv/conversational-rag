# Step 6, phase 2: graph retrievers and QA on dev-500

This report compares several ways of using the knowledge graph for retrieval with the best Step 4 pipeline (hybrid retrieval + query rewriting + reranking, agent-style prompt). Everything else is kept the same as in Step 4: dev-500, the generator (`gpt-5.4-nano`), the prompt and its few-shot examples, the raw user turn as the question in the prompt, five sections of context, and the evaluator in `experiments/evaluate_diagnostics.py`. The Step 4 baseline was regenerated from the cache (934 hits, no misses) and gives exactly the same numbers as before (F1 28.0, R@5 67.4).

Code is in `src/kg_rag/` (`retrievers.py`, `run_qa.py`, `eval_qa.py`). To reproduce:

```bash
python -m src.kg_rag.run_qa --workers 12
python -m src.kg_rag.eval_qa
```

The per-question results go to `experiments/results/dev_500/` (not tracked), the summaries to `phase2_retrieval.json` and `phase2_qa.json`.

## 1. Setup

Linking follows the phase 1 decisions: the rewritten query, the top-10 entities, hubs kept. The domain filter is not used except in C, because the predicted domain comes from Step 4 retrieval and would mix passage retrieval into the graph results.

Each linked entity e gets a weight `w(e) = link(e) * log(1 + N / sections(e))`, where `link(e)` is the RRF linking score and N = 3,355 is the number of sections with at least one entity. The log term down-weights entities that are mentioned in many sections.

The pipelines:

* A: from the linked entities to their sections. A section scores the sum of `w(e)` over the linked entities it mentions; the top 5 are the context. A variant adds the neighbours of non-hub linked entities (1-hop) with half the link score.
* B: the relations of the linked entities (their 1-hop subgraph) as facts, ranked by RRF of the endpoint weight and the query-fact cosine (bge-small). The top 30 are given as triples with one evidence quote each, without any raw section.
* C: RRF of A (linked with the domain filter) and the Step 4 ranking, top-50 each, then reranked by the Step 4 cross-encoder.
* D: A's top-50 (31 sections on average) reranked by the same cross-encoder, so the graph replaces BM25 + dense as the candidate generator.
* E: the Step 4 top-5 sections unchanged, followed by B's facts in a separate "Facts:" block. The sections part was checked to be identical to the Step 4 context for all 500 questions.
* E-random: a control for E. Same sections, plus the same number of facts drawn at random from the facts of the question's domain (seed 42 per question).

All parameters (10 entities, decay 0.5, 30 facts, pools of 50) were fixed before running. For B, recall is computed on the sections the facts come from, in fact order. B's context has 25.9 facts on average and is never empty.

## 2. Results

dev-500, n = 500. ΔF1 is the paired bootstrap difference to Step 4 with its 95% interval; it counts as significant when the interval excludes 0. F1 hit/miss is on answerable questions with and without a gold span in the pipeline's own top-5.

| Pipeline | R@1 | R@5 | F1 | F1 hit / miss | Abstain | ΔF1 vs Step 4 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Step 4 best | 38.0 | 67.4 | 28.0 | 33.3 / 17.4 | 6.4 | - |
| A: sections | 14.4 | 34.6 | 24.5 | 33.5 / 18.4 | 10.6 | -3.5 [-5.1, -1.9] |
| A with 1-hop | 12.6 | 36.6 | 23.5 | 33.0 / 18.0 | 8.6 | -4.5 [-6.3, -2.8] |
| B: facts | 15.6 | 37.2 | 25.4 | 30.0 / 20.9 | 9.6 | -2.7 [-4.4, -0.8] |
| C: hybrid | 37.8 | 67.6 | 27.6 | 33.3 / 17.1 | 6.0 | -0.5 [-1.2, 0.1] |
| D: KG candidates reranked | 35.8 | 58.8 | 26.4 | 33.3 / 18.7 | 6.4 | -1.6 [-2.9, -0.4] |
| E: Step 4 sections + facts | 38.0 | 67.4 | **29.2** | 34.1 / 18.7 | 5.8 | +1.1 [-0.3, 2.5] |
| E-random | 38.0 | 67.4 | 29.1 | 33.3 / 18.1 | 8.4 | +1.0 [-0.3, 2.4] |

Abstention recall on the 31 unanswerable turns / false abstention on answerable ones: Step 4 25.8 / 5.1, A 38.7 / 8.7, A 1-hop 22.6 / 7.7, B 41.9 / 7.5, C 19.4 / 5.1, D 12.9 / 6.0, E 29.0 / 4.3, E-random 38.7 / 6.4.

Graph-only retrieval (A, B) finds the gold section about half as often as Step 4 and loses 2.7 to 4.5 F1 points. The problem is ranking, not linking: A's candidates contain the gold section for 68.8% of the questions (R@50, close to the 70.4% link recall), but the top-5 only for 34.6%. Step 4 finds the gold section in 179 questions where A misses it, A only in 15 where Step 4 misses it. Entity overlap is the only signal the graph gives for ranking, and a typical question links entities that appear in tens of sections. When A does retrieve the gold section, the answer is as good as with Step 4 (33.5 vs 33.3), so the whole F1 loss comes from the lower hit rate.

1-hop expansion adds 2 points of R@5 but loses 1 point of F1 (-1.0 [-2.4, 0.3] vs A): the neighbour sections are on related topics but rarely contain the answer.

Facts (B) are the best graph-only context, +0.9 over A (not significant). They hold up better when the gold section is missed (F1 on misses 20.9, against 18.4 for A and 17.4 for Step 4): about 26 facts from about 15 sections still carry pieces of the answer, and in 48.8% of the questions at least one fact comes from the gold section. When the gold section is found they lose detail, since a triple and one quote are shorter than the section (30.0 vs 33.5).

The hybrid C is indistinguishable from Step 4. The cross-encoder rarely prefers a section found only through the graph: they fill 0.12 of the 5 slots on average and the context changes in only 62 questions. On those 62, R@5 goes up a little (56.5 vs 54.8) but F1 goes down (23.3 vs 27.2, -4.0 [-9.2, 0.5]).

Graph contexts also make the model abstain more (9.6-10.6% of the answers for A and B, 6.4% for Step 4). This catches more unanswerable turns but gives more false abstentions, a sign that the context is less often relevant.

## 3. D, E and the random-facts control

For these comparisons hit/miss means whether the Step 4 top-5 contains a gold span, so the partition is the same for every pipeline and the tests stay paired.

| Split (n) | Step 4 F1 | D: ΔF1 | E: ΔF1 | E-random: ΔF1 | E-random vs E |
| :--- | :---: | :---: | :---: | :---: | :---: |
| All (500) | 28.0 | -1.6 [-2.9, -0.4] | +1.1 [-0.3, 2.5] | +1.0 [-0.3, 2.4] | -0.1 [-1.1, 1.1] |
| Answerable (469) | 28.1 | - | +0.9 [0.0, 1.8] | +0.2 [-0.6, 1.0] | -0.7 [-1.6, 0.2] |
| Step 4 hit (316) | 33.3 | -2.1 [-3.6, -0.7] | +0.7 [-0.5, 1.9] | 0.0 [-1.1, 1.1] | -0.7 [-2.0, 0.4] |
| Step 4 miss (153) | 17.4 | +1.6 [0.2, 3.0] | +1.3 [0.1, 2.6] | +0.7 [-0.4, 1.9] | -0.6 [-1.8, 0.6] |
| Same document (406) | 28.0 | -1.8 [-3.3, -0.5] | +1.2 [-0.4, 2.9] | +1.1 [-0.6, 2.7] | -0.1 [-1.3, 1.1] |
| Doc switch (94) | 28.4 | -0.9 [-3.7, 1.7] | +0.7 [-0.9, 2.5] | +0.8 [-1.1, 2.5] | +0.1 [-1.8, 2.0] |
| Unanswerable (31) | 26.7 | -12.9 [-25.6, -3.0] | +3.7 [-12.2, 19.8] | +13.0 [-3.1, 29.1] | +9.3 [-0.3, 22.2] |

D, the graph as a candidate generator: the reranker fixes most of A's ranking problem (R@5 from 34.6 to 58.8), but the graph candidates contain the gold section for 68.8% of the questions against 88.6% for the Step 4 top-50, and F1 ends up 1.6 points lower. D changes the context in 405 questions and loses more gold sections than it gains (R@5 on those 54.6 vs 65.2). It helps where Step 4 misses (+1.6) and hurts where Step 4 hits (-2.1). It also rarely abstains on unanswerable turns (12.9%), which costs 12.9 points there.

E, facts added to the Step 4 sections, is the only variant above Step 4 (+1.1, not significant, one-sided p = 0.054). The gain is significant where Step 4 misses the gold section (+1.3), and there is no loss where it hits. The prompt is 2.3 times longer (15,082 characters vs 6,598).

The control shows that the overall gain of E is not evidence that the facts help: random facts gain as much (+1.0, and E-random vs E is -0.1). The tie hides two effects that go in opposite directions. Random facts make the model abstain more (8.4% vs 5.8% for E), which pays on the 31 unanswerable turns (whose reference is the abstention phrase) and costs false abstentions on the answerable ones (6.4% vs 4.3%). On answerable turns the real facts help (+0.9 [0.0, 1.8]) and random ones don't (+0.2).

Splitting the answerable questions by whether E's facts reach a gold section (exploratory, since the split is defined by E, but both variants are compared on the same questions with the same number of facts):

| Subset (n) | E vs Step 4 | E-random vs Step 4 | E vs E-random |
| :--- | :---: | :---: | :---: |
| E's facts reach a gold section (228) | +2.0 [0.7, 3.5] | +0.2 [-1.1, 1.6] | +1.8 [0.3, 3.4] |
| They don't (241) | -0.1 [-1.4, 1.0] | +0.2 [-0.8, 1.3] | -0.4 [-1.6, 0.7] |

So the content of the facts matters only where they come from the gold section. Random facts reach a gold section in just 16 of the 469 answerable questions. By domain E-random is close to E (DMV 34.6 vs 35.3, SSA 28.8 vs 27.8, StudentAid 25.2 vs 25.9, VA 27.7 vs 27.7), so part of E's DMV gain is a context effect.

## 4. Splits

F1 / R@5 / ΔF1 vs Step 4 by turn type:

| Pipeline | Same document (406) | Doc switch (94) | Unanswerable (31): F1 / abstain / ΔF1 |
| :--- | :--- | :--- | :--- |
| Step 4 best | 28.0 / 67.7 / - | 28.4 / 66.0 / - | 26.7 / 25.8 / - |
| A | 24.6 / 36.0 / -3.3 | 24.0 / 28.7 / -4.4 | 39.3 / 38.7 / +12.6 |
| A with 1-hop | 23.2 / 37.7 / -4.7 | 24.7 / 31.9 / -3.7 | 23.7 / 22.6 / -3.0 |
| B | 25.3 / 38.4 / -2.7 | 25.9 / 31.9 / -2.5 | 42.5 / 41.9 / +15.7 |
| C | 27.5 / 68.0 / -0.5 | 27.8 / 66.0 / -0.7 | 20.3 / 19.4 / -6.5 |
| D | 26.2 / 61.1 / -1.8 | 27.5 / 48.9 / -0.9 | 13.9 / 12.9 / -12.9 |
| E | 29.2 / 67.7 / +1.2 | 29.1 / 66.0 / +0.7 | 30.4 / 29.0 / +3.7 |
| E-random | 29.1 / 67.7 / +1.1 | 29.2 / 66.0 / +0.8 | 39.8 / 38.7 / +13.0 |

The graph loses most on doc-switch turns (A R@5 28.7 vs 66.0), because the rewrite carries the previous topic into linking (phase 1, section 4), while passage retrieval and reranking recover. The unanswerable turns gain F1 under A and B only through the extra abstentions; with 31 examples the intervals are wide and only D's loss there is significant.

F1 by domain:

| Pipeline | DMV | SSA | StudentAid | VA |
| :--- | :---: | :---: | :---: | :---: |
| Step 4 best | 31.8 | 28.0 | 24.7 | 27.7 |
| A | 30.9 | 22.3 | 22.9 | 22.0 |
| A with 1-hop | 29.3 | 19.7 | 23.2 | 21.9 |
| B | 29.7 | 24.3 | 24.0 | 23.5 |
| C | 31.1 | 28.1 | 23.6 | 27.5 |
| D | 31.4 | 25.3 | 23.4 | 25.6 |
| E | 35.3 | 27.8 | 25.9 | 27.7 |
| E-random | 34.6 | 28.8 | 25.2 | 27.7 |

The graph comes closest in DMV (A -0.9), where questions often name a specific document or fee that links to few sections. SSA and VA are furthest behind (-5.7 each for A): their questions link broad services like "Social Security benefits" or "VA health care", the hubs from phase 1.

## 5. An example

For "What VA dental care benefits do I qualify for?", B's top facts start with the hub "VA health care" (two general facts about eligibility), followed by the right facts from the gold section ("Class V applies to dental care ... needed to achieve at least one of the goals listed below", with the quote "The dental care must be needed to: Make it possible for you to be in the vocational rehab program"). The answer is correct in substance but longer than the reference and mixes in the general facts. The hub still takes the top slots because it links strongly.

## 6. Cost

No pipeline adds LLM calls: 0.87 rewrite calls (turns with history) and one generation per question, as in Step 4. Linking and scoring take 7-8 ms per question on CPU. Reranking for C took 312 ms per question for the pairs not already scored by Step 4, and 466 ms for D (uncached). Mean prompt length: Step 4 6,598 characters, A 7,947, A 1-hop 8,132, B 9,649, C 6,669, D 7,047, E 15,082.

Generation latency was not measured, since part of the answers came from the shared cache. New LLM calls: 1,548 for A-C (452 C prompts were identical to Step 4), 892 for D and E, 500 for E-random. `phase2_retrieval.json` comes from the last run, where all reranker scores were cached, so its reranking times are lower than the ones above.

## 7. Section-frequency weighting

A quick retrieval-only check after the runs (not used to choose anything):

| A variant | R@1 | R@5 | R@10 | R@50 |
| :--- | :---: | :---: | :---: | :---: |
| with log weighting (used) | 14.4 | 34.6 | 47.6 | 68.8 |
| with log weighting, 1-hop (used) | 12.6 | 36.6 | 48.8 | 73.0 |
| without | 15.6 | 36.6 | 50.4 | 68.4 |
| without, 1-hop | 12.6 | 36.0 | 47.2 | 71.6 |

The weighting doesn't help; without it R@5 is 2 points higher, within noise. The link score already demotes loosely related hubs, and the remaining hub links are mostly about the hub itself.

## 8. Conclusions

* Retrieval over the graph alone is worse than passage retrieval on MultiDoc2Dial (-2.7 to -4.5 F1). Linking finds the right topic for 70% of the questions, but entity overlap can't rank the ~30 sections it reaches, and the answers are passages rather than single facts.
* Facts are the better graph context: more robust when the gold section is missed, but less detailed when it's found.
* The hybrid C matches Step 4 without improving it, and using the graph as a candidate generator (D) is worse than BM25 + dense.
* Adding facts to the Step 4 sections (E) gains as much as adding random facts. On answerable questions the real facts help (+0.9), and where they come from a gold section they beat random facts by 1.8 points. So the graph helps only when its facts reach the answer.
* For Graph RAG (Step 7) this means: fewer and better-ranked facts, a matched random control, answerable and unanswerable turns reported separately, and a check beyond dev-500. Using the graph to choose sections within the linked document after a doc switch is still untested.

The main results were later confirmed on the full validation split and the held-out test split, where the gain of E on answerable questions becomes significant (`experiments/final_evaluation_report.md`).

Limitations of this report: dev-500 only and 31 unanswerable turns; token F1 penalises the longer answers built from facts; parameters were not tuned; the graph has about 73% triple precision on unseen documents; many splits are compared without correction, so the D/E splits are exploratory; E-random uses one random draw per question.
