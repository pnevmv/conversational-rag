# Retrieval ablation (dev-500, no LLM calls)

Section recall; ΔR@5 is the paired bootstrap difference to the current pipeline (bge-small, hybrid + reranker).

| Variant | R@1 | R@5 | R@10 | R@50 | ΔR@5 [95% CI] |
| :--- | :---: | :---: | :---: | :---: | :---: |
| bge-small-en-v1.5, dense only | 31.2 | 59.2 | 67.2 | 87.0 | -8.2 [-12.0, -4.4] |
| bge-small-en-v1.5, hybrid, no reranker | 32.4 | 60.4 | 72.8 | 88.6 | -7.0 [-10.4, -3.6] |
| bge-small-en-v1.5, hybrid + reranker | 37.6 | 67.4 | 75.4 | 88.6 | - |
| bge-small-en-v1.5, RRF(reranker, hybrid) | 36.0 | 67.4 | 74.8 | 88.6 | +0.0 [-2.6, 2.6] |
| bge-small-en-v1.5, 0.3 reranker + 0.7 hybrid | 36.4 | 66.0 | 74.4 | 88.6 | -1.4 [-4.4, 1.6] |
| bge-small-en-v1.5, 0.5 reranker + 0.5 hybrid | 36.6 | 66.6 | 75.0 | 88.6 | -0.8 [-3.4, 1.8] |
| bge-small-en-v1.5, 0.7 reranker + 0.3 hybrid | 36.4 | 67.6 | 75.0 | 88.6 | +0.2 [-2.0, 2.4] |
| bge-base-en-v1.5, dense only | 31.6 | 59.0 | 71.0 | 87.0 | -8.4 [-11.8, -4.6] |
| bge-base-en-v1.5, hybrid, no reranker | 33.2 | 62.0 | 71.2 | 88.2 | -5.4 [-9.0, -2.2] |
| bge-base-en-v1.5, hybrid + reranker | 38.6 | 66.4 | 75.2 | 88.2 | -1.0 [-2.4, 0.2] |
| bge-base-en-v1.5, RRF(reranker, hybrid) | 36.0 | 65.4 | 74.4 | 88.2 | -2.0 [-4.6, 0.6] |
| bge-base-en-v1.5, 0.3 reranker + 0.7 hybrid | 37.4 | 64.4 | 72.4 | 88.2 | -3.0 [-6.0, 0.0] |
| bge-base-en-v1.5, 0.5 reranker + 0.5 hybrid | 38.4 | 66.0 | 75.0 | 88.2 | -1.4 [-4.0, 1.2] |
| bge-base-en-v1.5, 0.7 reranker + 0.3 hybrid | 37.4 | 66.8 | 75.6 | 88.2 | -0.6 [-3.0, 1.8] |
| bge-large-en-v1.5, dense only | 34.2 | 62.4 | 71.2 | 88.2 | -5.0 [-8.4, -1.4] |
| bge-large-en-v1.5, hybrid, no reranker | 33.2 | 61.8 | 72.6 | 88.6 | -5.6 [-9.0, -2.2] |
| bge-large-en-v1.5, hybrid + reranker | 38.2 | 67.4 | 75.0 | 88.6 | +0.0 [-1.0, 1.2] |
| bge-large-en-v1.5, RRF(reranker, hybrid) | 37.0 | 66.8 | 74.6 | 88.6 | -0.6 [-3.0, 1.8] |
| bge-large-en-v1.5, 0.3 reranker + 0.7 hybrid | 37.8 | 66.2 | 73.4 | 88.6 | -1.2 [-4.2, 2.0] |
| bge-large-en-v1.5, 0.5 reranker + 0.5 hybrid | 37.4 | 66.4 | 74.8 | 88.6 | -1.0 [-3.6, 1.4] |
| bge-large-en-v1.5, 0.7 reranker + 0.3 hybrid | 36.2 | 66.8 | 75.0 | 88.6 | -0.6 [-3.0, 1.8] |
| e5-large-v2, dense only | 35.0 | 59.8 | 69.6 | 86.8 | -7.6 [-11.2, -3.8] |
| e5-large-v2, hybrid, no reranker | 32.8 | 61.8 | 71.0 | 89.0 | -5.6 [-8.8, -2.6] |
| e5-large-v2, hybrid + reranker | 37.6 | 67.0 | 75.4 | 89.0 | -0.4 [-1.8, 1.2] |
| e5-large-v2, RRF(reranker, hybrid) | 35.6 | 65.2 | 74.8 | 89.0 | -2.2 [-4.6, 0.2] |
| e5-large-v2, 0.3 reranker + 0.7 hybrid | 37.2 | 64.6 | 73.6 | 89.0 | -2.8 [-5.6, 0.0] |
| e5-large-v2, 0.5 reranker + 0.5 hybrid | 36.6 | 65.4 | 74.6 | 89.0 | -2.0 [-4.4, 0.6] |
| e5-large-v2, 0.7 reranker + 0.3 hybrid | 36.2 | 66.2 | 76.0 | 89.0 | -1.2 [-3.4, 0.8] |
