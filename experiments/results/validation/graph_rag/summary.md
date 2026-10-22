# Step 7: Graph RAG variants (validation)

gpt-5.4-nano, G2 + abstain(G0) in every system; P and E are the cached answers of the generator-input experiment. Δ: paired bootstrap difference with its 95% interval. The two subsets are fixed as defined for E in the graph analysis: 'miss + gold fact' = gold section not in the passage top 5 and one of E's facts from it (342 questions); 'hit, no gold fact' = gold section in the top 5 and none of E's facts from it (1005). Generator tokens per turn: G0 always, G2 when G0 does not abstain, counted from the prompts and answers (o200k_base), so P, E and the variants are counted the same way; the rewrite (~190 input tokens per turn) is the same for all and left out. No reasoning tokens: gpt-5.4-nano used none in the measured runs.

V1 thresholds, chosen on dev-500 by F1 (ties go to the higher threshold): k = 5: 0.0; k = 10: 0.0. Dev-500 F1 per setting: k5_t0.0 29.6, k5_t0.05 29.3, k5_t0.2 29.5, k5_t0.5 29.3, k10_t0.0 30.2, k10_t0.05 29.5, k10_t0.2 29.5, k10_t0.5 29.6.

### Full validation split (n = 4427)

| System | F1 all | answerable | unanswerable | Δ all vs P | Δ all vs E | Δ answerable vs E | miss + gold fact (Δ vs E) | hit, no gold fact (Δ vs E) | abstain recall / false abstention | gen. tokens / turn in / out | in vs E |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| P: passages | 27.5 | 27.6 | 25.0 | - | -0.5 [-0.9, -0.1] | -0.6 [-0.9, -0.3] | 20.6 (-4.6 [-6.6, -2.7]) | 31.9 (+1.0 [0.1, 1.9]) | 24.3 / 5.6 | 2481 / 101 | -57% |
| E: passages + 30 facts | 28.0 | 28.2 | 24.5 | +0.5 [0.1, 0.9] | - | - | 25.2 (-) | 30.9 (-) | 23.5 / 4.6 | 5775 / 98 | +0% |
| V0: graph facts only (B) | 24.6 | 24.1 | 33.9 | -2.9 [-3.5, -2.3] | -3.4 [-3.9, -2.8] | -4.1 [-4.5, -3.6] | 26.5 (+1.2 [-0.2, 2.7]) | 22.3 (-8.6 [-9.9, -7.3]) | 33.2 / 10.0 | 3741 / 80 | -35% |
| V1: top 5 facts | 27.6 | 28.1 | 18.3 | +0.1 [-0.2, 0.5] | -0.4 [-0.8, -0.0] | -0.1 [-0.4, 0.2] | 22.7 (-2.5 [-4.5, -0.7]) | 30.7 (-0.2 [-1.0, 0.6]) | 17.3 / 3.7 | 3162 / 101 | -45% |
| V1 control: 5 random facts | 27.8 | 27.3 | 36.4 | +0.3 [-0.1, 0.7] | -0.2 [-0.7, 0.2] | -0.9 [-1.2, -0.6] | 21.6 (-3.6 [-5.5, -1.7]) | 31.7 (+0.8 [-0.1, 1.7]) | 35.8 / 6.6 | 3089 / 99 | -47% |
| V1: top 10 facts | 28.0 | 28.3 | 22.5 | +0.5 [0.1, 0.9] | -0.0 [-0.4, 0.4] | +0.1 [-0.2, 0.4] | 23.2 (-2.0 [-4.0, -0.1]) | 30.8 (-0.0 [-0.9, 0.9]) | 21.2 / 3.9 | 3778 / 99 | -35% |
| V1 control: 10 random facts | 28.1 | 27.6 | 36.4 | +0.6 [0.2, 0.9] | +0.1 [-0.4, 0.5] | -0.6 [-0.9, -0.3] | 21.5 (-3.7 [-5.5, -1.9]) | 32.1 (+1.2 [0.3, 2.0]) | 36.3 / 6.6 | 3713 / 97 | -36% |
| V2a: 10 facts, out-of-context first | 27.8 | 28.0 | 23.7 | +0.3 [-0.1, 0.7] | -0.2 [-0.6, 0.2] | -0.2 [-0.5, 0.1] | 25.5 (+0.3 [-1.7, 2.3]) | 30.6 (-0.3 [-1.3, 0.6]) | 23.0 / 4.3 | 3753 / 99 | -35% |
| V2b: 5 out-of-context + 5 in-context | 27.9 | 28.2 | 23.2 | +0.5 [0.1, 0.8] | -0.1 [-0.4, 0.3] | +0.0 [-0.3, 0.3] | 23.2 (-2.0 [-3.8, -0.3]) | 30.9 (-0.0 [-0.9, 0.8]) | 22.1 / 3.9 | 3770 / 99 | -35% |

### Held-out validation (dev-500 removed), for the tuned V1 settings (n = 3927)

| System | F1 all | answerable | unanswerable | Δ all vs P | Δ all vs E | Δ answerable vs E | miss + gold fact (Δ vs E) | hit, no gold fact (Δ vs E) | abstain recall / false abstention | gen. tokens / turn in / out | in vs E |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| P: passages | 27.2 | 27.4 | 23.2 | - | -0.5 [-1.0, -0.1] | -0.6 [-0.9, -0.3] | 20.5 (-4.4 [-6.4, -2.4]) | 31.3 (+0.7 [-0.2, 1.6]) | 22.6 / 5.6 | 2481 / 101 | -57% |
| E: passages + 30 facts | 27.7 | 28.0 | 22.6 | +0.5 [0.1, 1.0] | - | - | 24.9 (-) | 30.6 (-) | 21.5 / 4.6 | 5775 / 98 | +0% |
| V0: graph facts only (B) | 24.5 | 24.1 | 31.7 | -2.7 [-3.3, -2.1] | -3.2 [-3.8, -2.6] | -3.8 [-4.3, -3.4] | 26.2 (+1.3 [-0.2, 2.9]) | 22.1 (-8.5 [-10.0, -7.1]) | 30.8 / 10.0 | 3741 / 80 | -35% |
| V1: top 5 facts | 27.4 | 27.9 | 16.4 | +0.2 [-0.2, 0.6] | -0.3 [-0.7, 0.0] | -0.0 [-0.3, 0.3] | 22.9 (-2.0 [-3.9, -0.2]) | 30.3 (-0.3 [-1.1, 0.6]) | 15.4 / 3.8 | 3162 / 101 | -45% |
| V1 control: 5 random facts | 27.5 | 27.1 | 34.9 | +0.3 [-0.1, 0.7] | -0.2 [-0.7, 0.2] | -0.9 [-1.2, -0.5] | 21.4 (-3.5 [-5.5, -1.5]) | 31.6 (+0.9 [0.0, 1.9]) | 34.4 / 6.5 | 3089 / 99 | -47% |
| V1: top 10 facts | 27.7 | 28.0 | 21.2 | +0.5 [0.1, 0.9] | -0.0 [-0.4, 0.4] | +0.1 [-0.2, 0.4] | 23.0 (-1.9 [-3.8, 0.0]) | 30.5 (-0.1 [-1.0, 0.9]) | 20.0 / 3.9 | 3778 / 99 | -35% |
| V1 control: 10 random facts | 27.8 | 27.3 | 35.6 | +0.6 [0.2, 1.0] | +0.1 [-0.4, 0.5] | -0.6 [-0.9, -0.3] | 21.3 (-3.6 [-5.6, -1.6]) | 32.0 (+1.3 [0.5, 2.2]) | 34.9 / 6.6 | 3713 / 97 | -36% |
| V2a: 10 facts, out-of-context first | 27.5 | 27.8 | 22.7 | +0.4 [-0.1, 0.8] | -0.2 [-0.6, 0.2] | -0.2 [-0.5, 0.2] | 25.9 (+1.0 [-0.7, 3.0]) | 30.1 (-0.5 [-1.4, 0.5]) | 22.1 / 4.3 | 3753 / 99 | -35% |
| V2b: 5 out-of-context + 5 in-context | 27.6 | 27.9 | 21.1 | +0.4 [0.0, 0.8] | -0.1 [-0.5, 0.3] | -0.1 [-0.4, 0.2] | 23.1 (-1.8 [-3.5, -0.1]) | 30.4 (-0.2 [-1.1, 0.6]) | 20.0 / 4.0 | 3770 / 99 | -35% |

### V1 against its random control (same number of facts per question)

| k | set | Δ all [95% CI] | Δ answerable [95% CI] |
| :--- | :--- | :---: | :---: |
| 5 | full | -0.1 [-0.6, 0.2] | +0.8 [0.5, 1.1] |
| 5 | held-out | -0.1 [-0.6, 0.3] | +0.8 [0.5, 1.1] |
| 10 | full | -0.1 [-0.5, 0.3] | +0.7 [0.4, 0.9] |
| 10 | held-out | -0.1 [-0.5, 0.4] | +0.7 [0.4, 1.0] |

### V2 against V1 with k = 10 (paired, full validation)

| System | Δ all | Δ answerable | Δ miss + gold fact | Δ hit, no gold fact | input tokens vs V1 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| V2a: 10 facts, out-of-context first | -0.2 [-0.5, 0.2] | -0.3 [-0.5, 0.0] | +2.4 [1.0, 3.9] | -0.2 [-0.8, 0.4] | -1% |
| V2b: 5 out-of-context + 5 in-context | -0.0 [-0.3, 0.2] | -0.1 [-0.3, 0.1] | +0.1 [-1.2, 1.5] | +0.0 [-0.6, 0.7] | -0% |

### Facts in the prompt (diagnostic, uses the gold sections)

| System | questions with a fact from a gold section | of them in the 342 'miss + gold fact' questions | facts per question |
| :--- | :---: | :---: | :---: |
| E: passages + 30 facts | 49.2% | 99.7% | 26.1 |
| V1: top 5 facts | 36.7% | 41.8% | 5.0 |
| V1 control: 5 random facts | 0.7% | 0.3% | 5.0 |
| V1: top 10 facts | 42.6% | 59.1% | 9.9 |
| V1 control: 10 random facts | 1.3% | 0.9% | 9.9 |
| V2a: 10 facts, out-of-context first | 9.2% | 69.6% | 9.9 |
| V2b: 5 out-of-context + 5 in-context | 45.0% | 56.4% | 9.9 |
