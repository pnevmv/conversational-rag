# LLM judge: gpt-6-luna, dev_500

Score: correct = 1, partial = 0.5, incorrect = 0. Abstentions are scored by rule. Supported: share of judged answers backed by the gold section or the context (agents: gold section only). Δ: paired bootstrap difference of the judge score to E, with its 95% interval.

| System | n | Judge score [95% CI] | Correct | Partial | Supported | Answerable | Unanswerable | Token F1 | Δ all vs E | Δ answerable vs E |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| LLM only, no documents | 500 | 27.9 [25.0, 30.8] | 8.8 | 38.2 | 1.8 | 28.5 | 19.4 | 16.3 | -40.2 [-44.5, -36.0] | -41.8 [-46.0, -37.6] |
| Gold section given | 500 | 81.4 [78.3, 84.3] | 71.2 | 20.4 | 91.3 | 85.7 | 16.1 | 36.3 | +13.3 [10.1, 17.0] | +15.5 [12.6, 18.7] |
| P: passages | 500 | 68.4 [64.8, 71.7] | 53.6 | 29.6 | 88.9 | 70.6 | 35.5 | 29.9 | +0.3 [-2.3, 3.1] | +0.3 [-2.2, 3.0] |
| E: passages + 30 facts | 500 | 68.1 [64.5, 71.3] | 52.0 | 32.2 | 86.3 | 70.3 | 35.5 | 30.4 | - | - |
| E with citations | 500 | 67.7 [64.3, 70.9] | 51.8 | 31.8 | 87.2 | 69.4 | 41.9 | 31.2 | -0.4 [-2.6, 1.8] | -0.9 [-3.2, 1.4] |
| V1: passages + 10 facts | 500 | 69.5 [66.2, 72.7] | 53.4 | 32.2 | 87.6 | 72.2 | 29.0 | 30.2 | +1.4 [-1.0, 3.8] | +1.9 [-0.2, 4.1] |
| A1 agent, abstain(G0) | 500 | 65.4 [62.2, 68.6] | 48.2 | 34.4 | 42.2 | 67.6 | 32.3 | 30.6 | -2.7 [-5.4, 0.1] | -2.7 [-5.2, -0.1] |
| A1 agent, own refusal | 500 | 47.9 [44.0, 51.5] | 36.8 | 22.2 | 47.5 | 46.8 | 64.5 | 24.6 | -20.2 [-23.8, -16.4] | -23.5 [-27.1, -20.0] |
| A2 agent, abstain(G0) | 500 | 62.5 [59.0, 66.0] | 45.0 | 35.0 | 40.0 | 64.5 | 32.3 | 29.7 | -5.6 [-8.1, -2.8] | -5.8 [-8.5, -3.1] |
| A2 agent, own refusal | 500 | 62.3 [58.9, 65.6] | 44.4 | 35.8 | 39.3 | 66.2 | 3.2 | 28.3 | -5.8 [-8.7, -2.7] | -4.1 [-6.9, -1.3] |
