# LLM judge: gpt-6-luna, test split

Final systems, evaluation only (nothing is re-selected). Score: correct = 1, partial = 0.5, incorrect = 0; abstentions are scored by rule. The judge (gpt-6-luna) is from the same model family as the generator (gpt-5.4-nano). Δ: paired bootstrap difference with its 95% interval. 241 of the questions are unanswerable. Questions without a verdict, left out: P 1 (content filter); E 1 (content filter); V1 1 (content filter).

| System | n | Judge score [95% CI] | Correct | Partial | Supported | Judge answerable | Judge unanswerable | Token F1 | F1 answerable |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| P: passages | 4334 | 67.3 [66.0, 68.4] | 53.0 | 28.4 | 88.5 | 69.6 | 27.4 | 27.6 | 27.5 |
| E: passages + 30 facts | 4334 | 68.5 [67.3, 69.6] | 53.2 | 30.7 | 88.1 | 71.2 | 23.7 | 28.2 | 28.4 |
| V1: passages + 10 facts | 4334 | 67.3 [66.1, 68.4] | 51.7 | 31.2 | 87.3 | 70.0 | 21.6 | 27.8 | 28.1 |

| Comparison | n | Δ judge all | Δ judge answerable | Δ judge unanswerable | Δ F1 all | Δ F1 answerable | Δ F1 unanswerable |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| V1 vs P | 4334 | +0.0 [-0.8, 0.9] | +0.4 [-0.5, 1.2] | -5.8 [-11.6, -0.4] | +0.2 [-0.2, 0.6] | +0.6 [0.3, 0.9] | -6.0 [-11.4, -0.9] |
| E vs P | 4334 | +1.3 [0.3, 2.2] | +1.6 [0.7, 2.4] | -3.7 [-9.5, 1.7] | +0.6 [0.2, 1.0] | +0.9 [0.5, 1.2] | -4.3 [-10.2, 1.1] |
| V1 vs E | 4334 | -1.2 [-2.0, -0.4] | -1.2 [-2.0, -0.4] | -2.1 [-7.1, 3.3] | -0.4 [-0.7, 0.0] | -0.3 [-0.6, 0.0] | -1.7 [-6.3, 3.6] |
