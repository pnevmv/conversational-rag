# V3: the graph as a reranker signal (retrieval only, validation)

Candidate sections: the 50 of the passage ranking plus the evidence sections of the candidate facts not among them (51171 new sections in total, 11.6 per question, scored with the same cross-encoder). Score s = ce + w * g, ce and g min-max normalised per question over the candidate pool; g = the best cross-encoder score of a candidate fact from that section (V1 scores), or A's entity-overlap score (summed weights of the linked entities the section mentions). w = 0 is the cross-encoder alone on the same pool. R@5 in %; Δ is the paired bootstrap difference to w = 0.

Passage ranking as used so far (top 5 of the 50, no new sections): R@5 63.7 on all, 63.3 held-out, 0.0 on the 342 'miss + gold fact' questions.

## Dev-500 grid (R@5)

| w | 0.0 | 0.05 | 0.1 | 0.2 | 0.3 | 0.5 | 0.75 | 1.0 | 1.5 | 2.0 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| best fact score | 67.8 | 64.8 | 64.2 | 63.2 | 63.4 | 62.2 | 60.6 | 58.6 | 56.8 | 54.6 |
| entity overlap | 67.8 | 65.4 | 65.0 | 64.4 | 62.8 | 61.2 | 60.2 | 58.4 | 54.8 | 52.2 |

R@5 on the fixed 'miss + gold fact' questions (all validation, diagnostic, not used for tuning):

| w | 0.0 | 0.05 | 0.1 | 0.2 | 0.3 | 0.5 | 0.75 | 1.0 | 1.5 | 2.0 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| best fact score | 3.5 | 16.7 | 21.3 | 29.5 | 33.3 | 39.5 | 44.4 | 45.9 | 47.1 | 48.0 |
| entity overlap | 3.5 | 12.0 | 18.1 | 22.2 | 25.4 | 30.4 | 37.1 | 38.9 | 42.7 | 43.0 |

Chosen on dev-500: g = best fact score, w = 0.0 (ties go to the smaller w).

## Held-out validation and the fixed subset

| Ranking | R@5 held-out (n = 3927) | Δ vs w = 0 | R@5 'miss + gold fact' (n = 342) | Δ vs w = 0 |
| :--- | :---: | :---: | :---: | :---: |
| passage ranking (top 5 of the 50) | 63.3 | +0.1 [-0.2, 0.4] | 0.0 | -3.5 [-5.6, -1.8] |
| w = 0, same pool | 63.2 | - | 3.5 | - |
| chosen: best fact score, w = 0.0 | 63.2 | - | 3.5 | - |
| best entity overlap on dev-500 (w = 0.0) | 63.2 | +0.0 [0.0, 0.0] | 3.5 | +0.0 [0.0, 0.0] |

Held-out R@5 gain of the chosen setting over w = 0: +0.0 points; on average 0.00 of the 5 sections change. Rule of the plan: generation only if this gain is at least 1 point.
