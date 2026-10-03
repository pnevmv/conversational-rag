# Step 6, Phase 2: KG Retrievers and QA on dev-500

Three retrievers over the full KG (A–C) and two cheap variants (D, E) are compared with the Step 4 best pipeline, Hybrid + Rewrite + Rerank with the agent-style prompt. Everything else is the same as Step 4: the dev-500 subset, the generator (`gpt-5.4-nano-smirnov`), the prompt with its few-shot examples, the raw user turn as the question in the prompt, the top-5 context size for section retrievers, and the evaluator (`experiments/evaluate_diagnostics.py`). The Step 4 baseline was regenerated from the cache (934 hits, 0 misses) and reproduces the published numbers exactly (F1 28.0, R@5 67.4).

Code:
- `src/kg_rag/retrievers.py` (retrievers), `run_qa.py` (retrieval and generation), `eval_qa.py` (evaluation);
- run with `python -m src.kg_rag.run_qa`, then `python -m src.kg_rag.eval_qa`;
- outputs: `experiments/results/dev_500/kg_*.jsonl` (Step 4 record schema, gitignored), `phase2_retrieval.json`, `phase2_qa.json`.

## 1. Retrievers

**Common linking step** (Phase 1 decisions):
- rewritten query, top-10 entities, hubs kept;
- **no domain filter for A, B, D and E**, since the predicted domain comes from Step 4 retrieval and would leak RAG into the KG-only results. C keeps the filter.

Each linked entity e gets a weight w(e) = link(e) · idf(e):
- link(e) is its RRF linking score;
- idf(e) = log(1 + N / sections(e)), where N = 3,355 sections have at least one entity. This is the section-frequency down-weighting: an entity mentioned in hundreds of sections (a hub) points to no section in particular.

**The retrievers:**

| | Retriever | Context |
| :--- | :--- | :--- |
| **A** | Linked entities → mentions → sections. A section scores the sum of w(e) over the linked entities it mentions (ties: more linked entities). | top-5 sections |
| **A, 1-hop** | As A, plus the neighbours of non-hub linked entities through entity relations, with weight 0.5 · link(e) · idf(neighbour). Hub neighbours are not added. | top-5 sections |
| **B** | The entity relations of the linked entities (1-hop subgraph), ranked by RRF of two rankings: the weight of their best linked endpoint, and the cosine between the query and the fact text (bge-small). | top-30 facts as triples, each with one evidence quote and its source page; no raw sections |
| **C** | RRF of A (linked with the domain filter) and the Step 4 ranking (top-50 each), then the Step 4 cross-encoder reranks the fused top-50 to the top-5. | top-5 sections |
| **D** | A's candidates (top-50, on average 31) reranked by the same cross-encoder (bge-reranker-base) to the top-5: the KG as candidate generator instead of BM25 + dense. | top-5 sections |
| **E** | The Step 4 best top-5 sections, unchanged, followed by B's facts for the same linked entities in a separate "Facts:" block. The sections part was checked to be identical to the Step 4 context for all 500 questions. | top-5 Step 4 sections + top-30 facts |

All parameters (10 entities, decay 0.5, 30 facts, top-50 pools) were fixed before the runs. For B, R@k is computed on the sections behind the facts, in fact order (the first evidence section of each fact). The context holds 25.9 facts on average and never comes out empty.

## 2. Results

dev-500, n = 500. CIs: 95% bootstrap. ΔF1 is the paired bootstrap against the Step 4 best; a difference is significant when its CI excludes 0.

| Pipeline | R@1 | R@5 [CI] | Domain R@5 | F1 [CI] | F1 hit (n) | F1 miss (n) | Abstain | Abstain recall | False abstain | ΔF1 vs Step 4 [CI] |
| :--- | ---: | :--- | ---: | :--- | :--- | :--- | ---: | ---: | ---: | :--- |
| **Step 4 best** (Hybrid + Rewrite + Rerank) | 38.0 | 67.4 [63.0, 71.2] | 93.7 | **28.0** [26.2, 29.9] | 33.3 (316) | 17.4 (153) | 6.4 | 25.8 | 5.1 | — |
| A: KG → sections | 14.4 | 34.6 [30.4, 38.4] | 88.3 | 24.5 [22.6, 26.3] | 33.5 (160) | 18.4 (309) | 10.6 | 38.7 | 8.7 | **−3.5** [−5.1, −1.9] |
| A: KG → sections, 1-hop | 12.6 | 36.6 [31.6, 40.8] | 89.6 | 23.5 [21.8, 25.3] | 33.0 (171) | 18.0 (298) | 8.6 | 22.6 | 7.7 | **−4.5** [−6.3, −2.8] |
| B: KG facts | 15.6 | 37.2 [32.8, 41.6] | 90.2 | 25.4 [23.6, 27.1] | 30.0 (173) | 20.9 (296) | 9.6 | 41.9 | 7.5 | **−2.7** [−4.4, −0.8] |
| C: hybrid (A + Step 4, reranked) | 37.8 | 67.6 [63.2, 71.4] | 93.8 | 27.6 [25.7, 29.4] | 33.3 (317) | 17.1 (152) | 6.0 | 19.4 | 5.1 | −0.5 [−1.2, 0.1] |
| D: A's top-50 reranked | 35.8 | 58.8 | 93.2 | 26.4 [24.6, 28.2] | 33.3 (274) | 18.7 (195) | 6.4 | 12.9 | 6.0 | **−1.6** [−2.9, −0.4] |
| **E: Step 4 sections + KG facts** | 38.0 | 67.4 | 93.7 | **29.2** [27.2, 31.0] | 34.1 (316) | 18.7 (153) | 5.8 | 29.0 | 4.3 | +1.1 [−0.3, 2.5] |

Hit/miss uses answerable examples: hit = a gold span in the pipeline's own top-5 sections. For B these are the top-5 fact sections; for E they are the Step 4 sections. Abstain is the share of all answers that abstain. §3 gives the D and E results with a common hit/miss partition.

**Main findings**

1. **KG-only retrieval finds half as many gold sections as Step 4** (R@5 35–37% vs 67%), and F1 drops by 2.7–4.5 points, all significant.
   - The gap is in ranking, not linking. A's candidates reach the gold section for 68.8% of the questions (R@50, close to the 70.4% link recall), but the top-5 reaches it for only 34.6%.
   - Step 4 finds the gold section in 179 examples where A misses it; A finds it in only 15 where Step 4 misses it.
   - The KG offers only entity overlap as a ranking signal, and a typical question links entities shared by tens of sections. The passage retriever and cross-encoder compare the whole question with the whole section.
2. **When A retrieves the gold section, it answers as well as Step 4** (F1 on hits 33.5 vs 33.3). The F1 loss is entirely the lower hit rate.
3. **1-hop expansion raises R@5 by 2 points but lowers F1 by 1 point** (A, 1-hop vs A: −1.0 [−2.4, 0.3], not significant). Neighbour sections add topic-adjacent but answer-poor context.
4. **Facts (B) are the best KG-only context:** +0.9 F1 over A (CI [−0.9, 2.7], not significant), despite no raw sections.
   - Facts hold up when the gold section is missed: F1 on misses is 20.9 vs 18.4 for A and 17.4 for Step 4. About 26 facts from about 15 sections carry pieces of the answer even without its section; the gold section is behind at least one fact in 48.8% of the questions.
   - Facts lose detail when it is found (F1 on hits 30.0 vs 33.5): a triple and one quote are shorter than the section.
5. **The hybrid (C) adds almost nothing to Step 4.**
   - The cross-encoder keeps the Step 4 top-5 nearly unchanged: KG-only sections take 0.12 of the 5 slots on average, and the context differs from Step 4 in only 62 of 500 questions.
   - On those 62 questions, R@5 rises slightly (56.5 vs 54.8) but F1 falls (23.3 vs 27.2; paired −4.0 [−9.2, 0.5], not significant).
   - Overall C is indistinguishable from Step 4 (−0.5 [−1.2, 0.1]).
6. **KG contexts make the generator abstain more:** 9.6–10.6% of answers for A and B vs 6.4% for Step 4. This catches more unanswerable turns (abstain recall 38.7–41.9% vs 25.8%) at the cost of more false abstentions (7.5–8.7% vs 5.1%), i.e. the contexts are less often relevant.

## 3. Variants D and E

**ΔF1 vs Step 4 by split.** Hit/miss here is the same partition for every pipeline: whether the **Step 4** top-5 contains a gold span (answerable turns only). This keeps the comparisons paired.

| Split (n) | Step 4 F1 | D: F1 / ΔF1 [CI] | E: F1 / ΔF1 [CI] |
| :--- | ---: | :--- | :--- |
| All (500) | 28.0 | 26.4 / **−1.6** [−2.9, −0.4] | 29.2 / +1.1 [−0.3, 2.5] |
| Step 4 hit (316) | 33.3 | 31.2 / **−2.1** [−3.6, −0.7] | 34.1 / +0.7 [−0.5, 1.9] |
| Step 4 miss (153) | 17.4 | 19.0 / **+1.6** [0.2, 3.0] | 18.7 / **+1.3** [0.1, 2.6] |
| Same document (406) | 28.0 | 26.2 / **−1.8** [−3.3, −0.5] | 29.2 / +1.2 [−0.4, 2.9] |
| Doc switch (94) | 28.4 | 27.5 / −0.9 [−3.7, 1.7] | 29.1 / +0.7 [−0.9, 2.5] |
| Unanswerable (31) | 26.7 | 13.9 / **−12.9** [−25.6, −3.0] | 30.4 / +3.7 [−12.2, 19.8] |

**Abstention:**

| | Abstain (all) | Abstain recall (unanswerable) | False abstain (answerable) |
| :--- | ---: | ---: | ---: |
| Step 4 best | 6.4 | 25.8 | 5.1 |
| D | 6.4 | 12.9 | 6.0 |
| E | 5.8 | 29.0 | 4.3 |

**D: KG as candidate generator.**
- The cross-encoder fixes most of A's ranking problem: R@5 rises from 34.6% (A) to 58.8%, but stays below Step 4 (67.4%). The KG candidate set is the limit: it holds the gold section for 68.8% of the questions, against 88.6% for the Step 4 top-50.
- F1 is 1.6 points below Step 4 (significant). D changes the context in 405 of 500 questions (1.9 of 5 sections differ on average), losing more gold sections than it gains (R@5 on those questions 54.6% vs 65.2%).
- D helps where Step 4 misses (+1.6, significant), which is the complementarity of the two candidate sources. But it loses more where Step 4 hits (−2.1).
- **Unanswerable turns:** D abstains least (abstain recall 12.9%), which costs 12.9 F1 points there. Reranked KG sections look relevant to the generator even when the answer is not in the corpus.

**E: facts added to the Step 4 context.**
- E is the only KG variant above Step 4: +1.1 F1 overall, with an interval that includes 0 (one-sided p = 0.054). It is not significant at the 95% level used throughout.
- **Where the gain comes from:** the gain is significant on the questions where Step 4 misses the gold section (+1.3 [0.1, 2.6]). There the facts are the only source of the answer, as in B (F1 on misses 18.7, close to B's 20.9). Where Step 4 hits, the facts neither help nor hurt (+0.7 [−0.5, 1.9]).
- **By whether the facts reach a gold section** (answerable turns; exploratory, the split depends on the KG):
  - +2.0 [0.7, 3.5] when at least one fact comes from a gold section (228 questions);
  - −0.1 [−1.4, 1.0] when none does (241).

  So the gain follows the facts' content, not just the longer context.
- **Abstention improves slightly in both directions:** fewer false abstentions (4.3% vs 5.1%) and more abstentions on unanswerable turns (29.0% vs 25.8%). Neither difference is tested; there are only 31 unanswerable turns.
- **By domain,** the gain is largest in DMV (+3.5) and StudentAid (+1.2). SSA and VA are unchanged (§4).
- **Cost:** the prompt is 2.3 times as long (15,082 characters vs 6,598). There are no extra LLM calls, and the facts retrieval adds 7–8 ms.

## 4. Splits

**By turn type:** F1, R@5 and ΔF1 vs Step 4 (n in brackets).

| Pipeline | Same document (406): F1 / R@5 / ΔF1 | Doc switch (94): F1 / R@5 / ΔF1 | Unanswerable (31): F1 / abstain / ΔF1 |
| :--- | :--- | :--- | :--- |
| Step 4 best | 28.0 / 67.7 / — | 28.4 / 66.0 / — | 26.7 / 25.8 / — |
| A | 24.6 / 36.0 / −3.3 [−5.3, −1.4] | 24.0 / 28.7 / −4.4 [−7.8, −1.3] | 39.3 / 38.7 / +12.6 [−2.9, 28.5] |
| A, 1-hop | 23.2 / 37.7 / −4.7 [−6.7, −2.7] | 24.7 / 31.9 / −3.7 [−6.7, −1.0] | 23.7 / 22.6 / −3.0 [−22.4, 15.5] |
| B | 25.3 / 38.4 / −2.7 [−4.8, −0.6] | 25.9 / 31.9 / −2.5 [−5.4, 0.2] | 42.5 / 41.9 / +15.7 [−0.7, 32.4] |
| C | 27.5 / 68.0 / −0.5 [−1.2, 0.1] | 27.8 / 66.0 / −0.7 [−2.0, 0.2] | 20.3 / 19.4 / −6.5 [−15.9, 0.1] |
| D | 26.2 / 61.1 / −1.8 [−3.3, −0.5] | 27.5 / 48.9 / −0.9 [−3.7, 1.7] | 13.9 / 12.9 / −12.9 [−25.6, −3.0] |
| E | 29.2 / 67.7 / +1.2 [−0.4, 2.9] | 29.1 / 66.0 / +0.7 [−0.9, 2.5] | 30.4 / 29.0 / +3.7 [−12.2, 19.8] |

- **Doc-switch turns:** the KG loses more retrieval recall on them (A: 28.7% vs 66.0%). The rewrite carries the previous topic into linking (Phase 1, §4), whereas the passage retriever and reranker recover from it.
- **Unanswerable turns** gain F1 under B and A because these contexts lead to more abstentions, and the reference answer of an unanswerable turn is the abstention phrase itself. With 31 examples the intervals are wide. Only D's loss there is significant.

**F1 by domain:**

| Pipeline | DMV | SSA | StudentAid | VA |
| :--- | ---: | ---: | ---: | ---: |
| Step 4 best | 31.8 | 28.0 | 24.7 | 27.7 |
| A | 30.9 | 22.3 | 22.9 | 22.0 |
| A, 1-hop | 29.3 | 19.7 | 23.2 | 21.9 |
| B | 29.7 | 24.3 | 24.0 | 23.5 |
| C | 31.1 | 28.1 | 23.6 | 27.5 |
| D | 31.4 | 25.3 | 23.4 | 25.6 |
| E | **35.3** | 27.8 | **25.9** | 27.7 |

- **DMV:** the KG comes closest here (A −0.9). Its questions often name a specific document or fee, which links to few sections.
- **SSA and VA:** the gap is largest (−5.7 and −5.7 for A). Their entities are broad, frequently mentioned services ("Social Security benefits", "VA health care"), the hubs of Phase 1.

## 5. Example (B)

Q: "What VA dental care benefits do I qualify for?" The top facts begin with the hub "VA health care" (two facts about eligibility in general), followed by the right facts from the gold section ("Dental care … needed to achieve at least one of the goals listed below", "Class V applies to …", with the evidence quote "The dental care must be needed to: Make it possible for you to be in the vocational rehab program"). The answer is correct in substance, but it is longer than the reference and mixes in the generic eligibility facts. This shows both the strength of facts (precise, sourced statements) and their weakness: the hub's own facts still take the top slots, because the fact ranking combines link weight and similarity, and the hub links strongly.

## 6. Cost and latency

| | Step 4 best | A / A, 1-hop | B | C | D | E |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| LLM calls per question | 0.87 rewrite + 1 generation | same | same | same | same | same |
| Retrieval latency (CPU, per question) | hybrid + reranking of 50 sections | 7–8 ms (linking + scoring) | 7–8 ms (+ fact embeddings once, 13,277 facts) | 15 ms + reranking (312 ms for the pairs not already scored by Step 4) | 7–8 ms + reranking of about 31 sections (466 ms, uncached) | Step 4 + 7–8 ms |
| Prompt size (characters, mean) | 6,598 | 7,947 / 8,132 | 9,649 | 6,669 | 7,047 | 15,082 |

- The KG retrievers add no LLM calls; the graph and the embeddings are built once.
- **Not measured:** generation latency, because most answers came from or went into the shared cache; and Step 4's own reranking time, because its scores were cached. The latencies above cover retrieval only.
- **Total LLM use in this phase:**
  - A–C: 1,548 new generation calls (452 C prompts were identical to Step 4 prompts and came from the cache), 236 s wall time with 12 workers.
  - D and E: 892 new calls (108 D prompts identical to Step 4), 381 s including the reranking.

## 7. Ablation: section-frequency down-weighting (retrieval only)

| A variant | R@1 | R@5 | R@10 | R@50 |
| :--- | ---: | ---: | ---: | ---: |
| idf weighting (used) | 14.4 | 34.6 | 47.6 | 68.8 |
| idf weighting, 1-hop (used) | 12.6 | 36.6 | 48.8 | 73.0 |
| no idf | 15.6 | 36.6 | 50.4 | 68.4 |
| no idf, 1-hop | 12.6 | 36.0 | 47.2 | 71.6 |

The down-weighting does not help: without it, R@5 is 2 points higher, within noise. The link score already demotes hubs that are only loosely related to the query, and the remaining hub links are mostly about the hub itself (Phase 1). These numbers were computed after the runs and were not used to choose the configuration.

## 8. Conclusions

- **KG-only retrieval loses to passage retrieval on this corpus** by 2.7–4.5 F1 points (significant). The graph links the right topic for 70% of the questions, but entity overlap is too coarse to rank the 30 or so sections it reaches, and the answers of MultiDoc2Dial are passages rather than facts.
- **Facts (B) are the better KG context:** more robust when the gold section is missed, but they lose detail when it is found.
- **The hybrid (C) matches Step 4 but does not improve it.** The cross-encoder rarely prefers a KG-only section, and when it does, F1 does not rise.
- **The KG as a candidate generator (D) is worse than BM25 + dense** (−1.6 F1, significant). Reranking fixes most of A's ranking, but the KG candidates reach fewer gold sections than the Step 4 pool (69% vs 89% at 50).
- **Adding facts to the Step 4 sections (E) is the most promising use of the KG:** +1.1 F1 overall, not significant (CI [−0.3, 2.5]). The gain is significant where Step 4 misses the gold section (+1.3) and where the facts reach it (+2.0, exploratory), with no loss where Step 4 already hits. This is the starting point for Step 7 (Graph RAG). Open questions there:
  - a control with the same number of random facts, to separate content from context length;
  - fewer, better-ranked facts, to shorten the 2.3-times-longer prompt;
  - confirmation beyond dev-500.
- **Not tested:** using the KG to rank sections within the linked document for doc-switch turns.

**Limitations.**
- dev-500 only; the unanswerable split has 31 examples.
- Token F1 penalises the longer answers built from facts.
- Retriever parameters were fixed without tuning.
- Several splits are compared, without correction for multiple comparisons. The split results for D and E, especially the split by facts reaching the gold section, are exploratory.
- The KG has about 53% triple precision on unseen documents (Step 5 control sample).
