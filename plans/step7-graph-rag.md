# Step 7: Graph RAG, plan

Validation only; the test split stays untouched. Every variant uses the same generator setup: `gpt-5.4-nano`, dialogue history with the abstention decision of the prompt without history (G2 + abstain(G0)). Retrieval, rewrites and linked entities are reused from the cache unless a variant changes them.

## Starting point

* P (passages) 27.5 F1, E (passages + up to 30 one-hop facts) 28.0, +0.5 [0.1, 0.9]. E-random shows that the gain on answerable questions comes from the content of the facts.
* The gain is concentrated where passage retrieval misses the gold section but a fact still comes from it: +4.6 on 342 questions. Where the passages hit and no fact comes from the gold section, E loses 1.0 (1,005 questions). A router on pre-generation signals does not separate the two (52% accuracy).
* Goal: keep the graph as a second retrieval channel for misses, and stop off-topic facts from adding noise when the passages are already right.
* Size of the problem: a question has on average 47 one-hop candidate facts (median 39, p95 120) from its 10 linked entities; the current 30 facts take about 1,670 prompt tokens (67 per fact).

## Variants

**V0. B with dialogue history.** Rerun graph facts only (B) with G2 + abstain(G0); B so far exists only with the user turn alone. No retrieval change. Cost: generation only, about the cost of P (~USD 2.6 on validation at list price). Control: none; it completes the comparison table.

**V1. Fact filtering.** Score every candidate fact ("source relation target" + evidence quote) against the rewritten query with the existing cross-encoder (bge-reranker-base). Keep the top k (k = 5 and k = 10), and drop facts below a score threshold chosen on dev-500. Why: the 30 facts are ranked by link weight and embedding similarity only; the cross-encoder already ranks sections well and should push off-topic facts out. Cost: ~47 cross-encoder pairs per question (~210k on validation, short texts, cached), no extra LLM call; the prompt shrinks by ~1,000-1,700 tokens per turn. Control: the same number of random facts from the same domain (E-random at k), so a gain is not just a shorter context.

**V2. Out-of-context facts first.** Among the facts kept by V1, prefer those whose evidence section is not among the top 5 passages (fill the remaining slots with in-context facts). Why: out-of-context facts are the ones that can recover a retrieval miss; in-context facts mostly repeat the passages. Cost: none beyond V1. Control: V1 alone at the same k.

**V3. Graph as a reranker signal** (the experiment promised to the professor). For each candidate section, combine the cross-encoder score with a graph score: s = ce(section) + w · g(section), with g the best V1 fact score whose evidence comes from that section, or the entity-overlap score of the linked entities (A's score); both normalised per question. Candidates: the 50 sections of the passage ranking plus the evidence sections of the candidate facts that are not among them. w and the choice of g are tuned on dev-500 by R@5, then reported on the other 3,927 validation questions. Generation with the new top 5 (sections only, and with the best V1/V2 facts). Cost: cross-encoder calls only for the few new candidate sections (cached), no extra LLM call. Control: w = 0 on the same candidate set (the cross-encoder alone), so a gain is not from the larger pool.

**V4 (optional). Two-hop paths.** Short chains between two linked entities through one intermediate entity, each with its evidence quotes. Only if V1-V3 leave a clear gap, checked first without any LLM call: count the retrieval misses where no one-hop fact but some two-hop path reaches a gold section. If that share is below ~10% of the misses, V4 is dropped.

## Measurement

* Metrics for every variant: token F1 on all / answerable / unanswerable questions, abstain recall and false abstention, R@5 where retrieval changes (V3), and input / output / reasoning tokens per turn from the usage log (cost at the list prices already used).
* Comparisons: paired bootstrap (95% interval) against P and against E on the same questions. For V1-V3 also the two subsets that motivate them: "miss, fact from the gold section" (342) and "hit, no fact from the gold section" (1,005), with the same definitions as the graph analysis.
* Tuned parameters (threshold, k, w) are chosen on dev-500 and reported on the other 3,927 validation questions; untuned variants are reported on the full split.
* The two subsets are fixed once, as defined for E in the graph analysis (gold section in the passage top 5, at least one of E's facts from a gold section), and are not recomputed per variant.
* Token savings (input and output tokens per turn of the generator, and the change against E in %) are reported next to F1 for every variant.
* Noise: picking the better of two runs of the same system gains ~2.9 F1, so per-question wins mean nothing. Only paired differences over the full held-out set count, and a difference of a few tenths with an interval that includes 0 is a tie.

## Stopping rules

* V1 is kept if, against E, F1 on answerable questions is not lower (Δ ≥ −0.2) and either the interval of Δ is above 0 or the prompt is at least 30% shorter; and it must beat its random control at the same k. Otherwise E stays.
* V2 is kept only if it improves on V1 at the same k on the "miss, fact from the gold section" subset without losing on all questions.
* V3 is kept if R@5 rises by at least 1 point over w = 0 on the held-out questions and F1 is not lower than P; if R@5 does not move, the graph is not a useful reranker signal and the result is reported as negative.
* Any variant that loses significantly to E on all questions is dropped.

## Order and budget

The final Step 7 system is chosen on validation only, then frozen and run once on the test split together with P and E, at the very end.


1. V0 (one run). 2. V1 retrieval-only (fact scores, k and threshold on dev-500), then generation. 3. V2 on top of V1. 4. V3 retrieval-only (R@5 on dev-500 and held-out), then generation only if R@5 improves. 5. V4 check, then V4 only if the gap exists.

Each generation run on validation costs about USD 2.6-4.8 at list price (between P and E) and 30-60 minutes; the whole plan is about 8-10 runs. Results go to `experiments/results/validation/graph_rag/` with a summary per variant.
