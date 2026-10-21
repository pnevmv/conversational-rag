# When does the graph help? (validation, cached outputs)

P = passages, E = passages + graph facts, both with the conversational generator (G2 + abstain(G0), gpt-5.4-nano, cached answers); B = graph facts only, which exists only with the current user turn (G0, no dialogue history). d = F1(E) - F1(P) per question, mean in points with a paired bootstrap 95% interval; d > 0 / d < 0 are the shares of questions where E is better / worse. Groups with fewer than 100 questions are not shown. n = 4427 questions, no new LLM calls.

Overall: F1 P 27.5, E 28.0, B 24.1; d = +0.5 [0.1, 0.9]; E better on 48%, worse on 42%, equal on 10%.

## 1. Where the graph facts help

**Dialogue act of the reference agent turn**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| respond_solution | 3210 | 30.5 | 31.2 | 26.2 | +0.6 [0.3, 1.0] | 49% | 44% |
| query_condition | 808 | 18.0 | 18.1 | 15.7 | +0.2 [-0.4, 0.7] | 49% | 42% |
| respond_no_solution | 226 | 25.0 | 24.5 | 30.6 | -0.5 [-6.8, 5.5] | 27% | 23% |
| respond_solution_positive | 103 | 25.6 | 26.5 | 23.0 | +1.0 [-0.5, 2.5] | 50% | 46% |

**Dialogue act of the user turn**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| query_condition | 2001 | 27.6 | 28.1 | 24.3 | +0.5 [0.1, 0.9] | 50% | 44% |
| query_solution | 1407 | 31.3 | 31.8 | 27.0 | +0.5 [-0.1, 1.1] | 48% | 44% |
| response_positive | 531 | 25.8 | 26.8 | 20.0 | +1.0 [0.1, 1.9] | 52% | 42% |
| response_negative | 488 | 17.9 | 18.0 | 19.8 | +0.2 [-2.9, 2.8] | 36% | 30% |

**Domain**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| va | 1269 | 26.9 | 27.8 | 24.2 | +0.9 [0.1, 1.7] | 49% | 41% |
| ssa | 1162 | 26.2 | 26.7 | 23.0 | +0.6 [-0.2, 1.2] | 48% | 41% |
| dmv | 1132 | 31.3 | 32.0 | 26.9 | +0.7 [-0.2, 1.6] | 47% | 43% |
| studentaid | 864 | 25.1 | 24.8 | 22.0 | -0.3 [-1.3, 0.6] | 47% | 43% |

**Position**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| follow-up | 3767 | 27.6 | 28.2 | 24.1 | +0.6 [0.1, 1.1] | 48% | 41% |
| first turn | 660 | 26.6 | 26.6 | 24.6 | -0.0 [-0.6, 0.7] | 50% | 46% |

**Document**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| same document | 3522 | 27.2 | 27.7 | 23.9 | +0.5 [-0.1, 1.0] | 48% | 42% |
| doc switch | 905 | 28.4 | 29.1 | 25.1 | +0.6 [-0.0, 1.3] | 50% | 43% |

**Passage retrieval (gold section in the top 5)**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| hit | 2822 | 32.5 | 32.6 | 26.7 | +0.1 [-0.4, 0.6] | 48% | 44% |
| miss | 1605 | 18.7 | 20.0 | 19.6 | +1.3 [0.6, 2.0] | 49% | 39% |

**At least one fact from a gold section**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| no | 2268 | 24.2 | 24.0 | 19.7 | -0.2 [-0.8, 0.3] | 45% | 44% |
| yes | 2159 | 30.9 | 32.2 | 28.8 | +1.3 [0.7, 1.9] | 52% | 40% |

**Hit and gold fact**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| hit, gold fact yes | 1817 | 32.8 | 33.5 | 29.3 | +0.7 [0.0, 1.3] | 50% | 41% |
| miss, gold fact no | 1263 | 18.1 | 18.5 | 17.8 | +0.4 [-0.4, 1.1] | 46% | 40% |
| hit, gold fact no | 1005 | 31.9 | 30.9 | 22.2 | -1.0 [-1.9, -0.1] | 43% | 48% |
| miss, gold fact yes | 342 | 20.6 | 25.2 | 26.2 | +4.6 [2.7, 6.6] | 59% | 34% |

**Number of facts**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 30 | 2891 | 27.5 | 28.1 | 24.4 | +0.5 [0.0, 1.0] | 49% | 42% |
| < 20 | 820 | 26.9 | 27.3 | 23.0 | +0.4 [-0.7, 1.6] | 45% | 43% |
| 20-29 | 716 | 28.0 | 28.6 | 24.2 | +0.6 [-0.5, 1.7] | 48% | 41% |

**Question names a linked entity (string match)**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| no | 2874 | 25.9 | 26.2 | 22.6 | +0.3 [-0.3, 0.9] | 47% | 41% |
| yes | 1553 | 30.4 | 31.3 | 27.1 | +0.9 [0.4, 1.4] | 50% | 43% |

**Answerable**

| Group | n | F1 P | F1 E | F1 B | d = E - P [95% CI] | d > 0 | d < 0 |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| answerable | 4201 | 27.6 | 28.2 | 23.8 | +0.6 [0.3, 0.9] | 49% | 43% |
| unanswerable | 226 | 25.0 | 24.5 | 30.6 | -0.5 [-6.8, 5.5] | 27% | 23% |

All questions have 10 linked entities, so the number of linked entities does not split them.

## 2. Oracle routers

Per question the better system is chosen with the reference answer, so this is an upper bound, not a usable system. Part of the gain is noise: two runs of the same system also differ per question.

| Router | F1 | gain over E [95% CI] |
| :--- | :---: | :---: |
| always P | 27.5 | -0.5 [-0.9, -0.1] |
| always E | 28.0 | - |
| oracle P / E | 31.3 | +3.3 [3.1, 3.6] |
| oracle P / E / B | 33.8 | +5.8 [5.5, 6.2] |
| oracle between two runs of E (noise reference) | 30.9 | +2.9 [2.7, 3.2] |

## 3. A cheap router between P and E

Fitted on the 500 dev-500 questions (labels: E better than P, ties left out), evaluated on the other 3927 validation questions. Features available before generation: top1, gap12, top5_mean, overlap, deg_mean, n_facts, turn, hist, q_len, first, switch, names_entity. top1/gap12/top5_mean are cross-encoder scores of the passage ranking, overlap is the share of facts whose evidence section is among the 5 passages, deg_mean the mean degree of the linked entities.

| Router (held-out validation) | F1 | vs always E [95% CI] | share routed to E |
| :--- | :---: | :---: | :---: |
| always P | 27.2 | -0.5 [-1.0, -0.1] | 0% |
| always E | 27.7 | - | 100% |
| logistic regression (threshold 0.553) | 27.2 | -0.5 [-0.8, -0.2] | 45% |
| single threshold: E if top1 <= 0.999 | 27.5 | -0.2 [-0.4, -0.0] | 80% |
| oracle P / E | 30.9 | +3.2 [3.0, 3.5] | - |

Logistic regression coefficients (standardised features, positive = E more likely better): names_entity -0.13, top5_mean -0.12, overlap +0.11, deg_mean +0.08, n_facts +0.07, top1 +0.06, switch -0.06, first +0.05, gap12 -0.03, turn -0.02, hist -0.02, q_len +0.01. Accuracy of the E-better label on held-out questions with d != 0: 52%.

## Conclusions

* **The graph facts help when passage retrieval misses the answer and a fact still comes from the gold section.** On these 342 questions E gains 4.6 points over passages (B alone does as well there). Over all retrieval misses the gain is 1.3 points; over the hits it is 0.1.
* **They hurt when the passages are already right and the facts are off-topic.** When the gold section is in the top 5 but no fact comes from it (1,005 questions), E loses 1.0 point: the extra facts distract from a good context.
* **Gains are small and spread out by question type.** E is ahead on follow-up turns (+0.6), on 'yes' replies of the user (+1.0), when the question names a linked entity (+0.9) and in the VA domain (+0.9); it gives nothing on first turns and in StudentAid. Per question, E is better on 48% and worse on 42%, so the average gain of 0.5 is the net of many changes in both directions.
* **A router is not worth it with these signals.** The oracle between P and E gains 3.3 points, but picking the better of two runs of the same system already gains 2.9, so almost all of the oracle gain is run-to-run variation. A logistic regression on features available before generation predicts the better system only 52% of the time and is 0.5 points worse than always using E; the best single threshold (top reranker score) is 0.2 points worse. The useful signal (whether a fact comes from the gold section) needs the gold answer and is not available at run time.
* **Graph facts only (B) are clearly worse overall** (24.1), but close to E where passage retrieval misses and a gold fact exists (26.2 vs 25.2); the three-way oracle gain (+5.8) is mostly noise too.
