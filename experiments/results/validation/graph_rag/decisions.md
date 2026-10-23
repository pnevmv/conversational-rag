# Step 7: decisions

Decisions taken with the stopping rules of `plans/step7-graph-rag.md`. The tables are in `summary.md`, which `experiments/graph_rag.py report` regenerates; this file is written by hand.

## V0 and V1

* **V0, graph facts only with dialogue history:** 24.6 F1, 3.4 points below E (24.1 without the history). It stays a reference row; on the questions where passage retrieval misses and a fact comes from the gold section it is as good as E (26.5 against 25.2, not significant), and on the questions where the passages hit and no fact does it loses 8.6 points.
* **V1 with k = 10: kept.** Same F1 as E on all and on answerable questions (−0.0 and +0.1, both ties) with 35% fewer generator input tokens, and 0.7 points better than 10 random facts on answerable questions. The dev-500 search kept no score threshold (every threshold was worse).
* **V1 with k = 5: dropped.** Same F1 as E on answerable questions with 45% fewer input tokens, but 0.4 points lower on all questions on the full split ([−0.8, −0.0]; held-out −0.3 [−0.7, 0.0]) because it abstains less (abstain recall 17% against 24%).
* **The filter removes the useful facts.** On the 342 questions where passage retrieval misses and one of E's facts comes from the gold section, V1 loses 2.0 (k = 10) and 2.5 (k = 5) points against E: the cross-encoder ranks facts that repeat the passages first, and the out-of-context facts that recovered the misses are cut. On the 1,005 questions where the passages are right, the off-topic facts were removed, but this did not recover the 1.0 point that E loses there (V1: −0.0 to −0.2 against E). This is the case V2 (out-of-context facts first) is meant to address.

## V2 (k = 10, out-of-context facts first)

Rule: V2 is kept only if it improves on V1 at the same k on the 342 "miss + gold fact" questions without losing on all questions.

* **V2a, all 10 slots out-of-context first: kept.** On the 342 questions it gains 2.4 points over V1 k = 10 ([1.0, 3.9]) and recovers E's level there (25.5 against 25.2); on all questions it is −0.2 against V1 ([−0.5, 0.2], not a significant loss), with the same tokens. Against E it ties on all and on answerable questions (−0.2 each, intervals include 0) with 35% fewer generator input tokens. The cost is on answerable questions in general (−0.3 against V1, [−0.5, 0.0]): when the passages already contain the answer, facts from the same sections helped a little.
* **V2b, 5 out-of-context + 5 in-context: dropped.** No gain on the 342 questions (+0.1 against V1) and no change elsewhere: V1's top 10 are already mostly out-of-context facts, so V2b selects almost the same facts.
* **Where this leaves Step 7:** no variant so far beats E on F1. V1 k = 10 and V2a both match E with 35% fewer input tokens; V2a keeps the recovery of retrieval misses, V1 is slightly better on answerable questions overall. V3 (the graph as a reranker signal) is next.

## V3 (the graph as a reranker signal, retrieval only)

Rule: generation only if the tuned setting raises held-out R@5 by at least 1 point over w = 0 on the same candidate pool.

* **No generation run; V3 is reported as a negative result.** Every w > 0 lowers dev-500 R@5 (67.8 at w = 0, 64.8 at w = 0.05, 54.6 at w = 2 with the fact score; the entity-overlap score behaves the same), so the tuned setting is w = 0 and the held-out gain is +0.0. The graph score is not a useful general reranker signal: added to the cross-encoder it mostly promotes sections that mention the linked entities but do not hold the answer.
* **Where it does help.** On the fixed 342 "miss + gold fact" questions, R@5 rises from 3.5 at w = 0 to 48.0 at w = 2. This subset is selected by one of E's facts coming from the gold section, which is what the fact score rewards, so the number is optimistic; it confirms the earlier finding that the graph signal is strong on a small group of questions that cannot be identified before generation.
* **Larger pool alone.** Adding the evidence sections of the candidate facts to the cross-encoder pool (w = 0) brings the gold section into the top 5 for 3.5% of the 342 questions, and leaves held-out R@5 unchanged (63.2 against 63.3 for the original top 5).
* **Step 7 so far:** V1 k = 10 (default) and V2a match E with 35% fewer generator input tokens; nothing beats E on F1.
