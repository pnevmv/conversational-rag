# Diagnostic Evaluation — MultiDoc2Dial

| Experiment | n | F1% [95% CI] | F1-hit% [CI] (n) | F1-miss% [CI] (n) | R@5% [CI] | Abstain Rec% [CI] | False Abstain% | Abstain Prec% |
|---|---|---|---|---|---|---|---|---|
| LLM-only | 500 | 16.3 [15.0–17.6] | — | — | — | 19.4 [6.5–35.5] | 7.7 | 14.3 |
| Oracle | 500 | 36.1 [34.0–38.4] | 36.7 [34.8–38.7] (n=469) | — | 100.0 [100.0–100.0] | 25.8 [9.7–41.9] | 4.1 | 29.6 |
| Oracle (agent prompt) | 500 | 36.3 [34.4–38.5] | 37.6 [35.6–39.6] (n=469) | — | 100.0 [100.0–100.0] | 16.1 [3.2–29.0] | 1.9 | 35.7 |
| RAG BM25 | 499 | 24.5 [22.4–26.4] | 36.0 [33.3–38.6] (n=193) | 14.2 [12.8–15.8] (n=275) | 39.1 [34.7–42.9] | 41.9 [25.8–58.1] | 15.4 | 15.3 |
| RAG Dense | 498 | 25.7 [23.5–28.0] | 35.1 [32.2–37.8] (n=189) | 12.8 [11.3–14.4] (n=278) | 38.4 [34.5–42.6] | 83.9 [71.0–93.5] | 22.1 | 20.2 |
| RAG Hybrid | 500 | 26.1 [24.1–28.1] | 35.4 [32.8–37.9] (n=214) | 13.9 [12.3–15.6] (n=255) | 43.2 [39.0–47.6] | 61.3 [41.9–77.4] | 16.0 | 20.2 |
| RAG Hybrid+Rewrite | 500 | 28.0 [26.2–30.0] | 33.3 [30.9–35.7] (n=286) | 18.3 [16.3–20.4] (n=183) | 61.2 [56.8–65.2] | 35.5 [19.4–51.6] | 7.0 | 25.0 |
| RAG Hybrid+Rewrite (agent prompt) | 500 | 27.8 [25.9–29.8] | 33.5 [31.3–35.9] (n=286) | 18.9 [17.0–21.0] (n=183) | 61.2 [56.8–65.2] | 29.0 [12.9–45.2] | 4.9 | 28.1 |
| RAG Hybrid+Rewrite+Rerank | 500 | 28.2 [26.3–30.0] | 33.4 [31.2–35.5] (n=316) | 16.8 [14.8–19.0] (n=153) | 67.4 [63.0–71.2] | 32.3 [16.1–51.6] | 6.8 | 23.8 |
| RAG Hybrid+Rewrite+Rerank (agent prompt) | 500 | 28.0 [26.2–29.9] | 33.3 [31.2–35.4] (n=316) | 17.4 [15.5–19.7] (n=153) | 67.4 [63.0–71.2] | 25.8 [12.9–41.9] | 5.1 | 25.0 |

## Paired Bootstrap Test: RAG Hybrid+Rewrite vs RAG Hybrid (Token F1, n=500)

Mean difference: +1.94 pp  95% CI [0.07–3.48]  p=0.017 (**significant**)

## Paired Bootstrap Test: Oracle (agent prompt) vs Oracle (Token F1, n=500)

Mean difference: +0.25 pp  95% CI [-0.87–1.32]  p=0.319 (not significant)

## Paired Bootstrap Test: RAG Hybrid+Rewrite (agent prompt) vs RAG Hybrid+Rewrite (Token F1, n=500)

Mean difference: -0.21 pp  95% CI [-1.68–1.35]  p=0.607 (not significant)

## Paired Bootstrap Test: RAG Hybrid+Rewrite+Rerank vs RAG Hybrid+Rewrite (Token F1, n=500)

Mean difference: +0.16 pp  95% CI [-1.27–1.60]  p=0.414 (not significant)

## Paired Bootstrap Test: RAG Hybrid+Rewrite+Rerank (agent prompt) vs RAG Hybrid+Rewrite (agent prompt) (Token F1, n=500)

Mean difference: +0.22 pp  95% CI [-1.13–1.56]  p=0.394 (not significant)
