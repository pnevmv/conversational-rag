# LLM judge: gpt-6-luna, validation split

Final systems, evaluation only (nothing is re-selected). Score: correct = 1, partial = 0.5, incorrect = 0; abstentions are scored by rule. The judge (gpt-6-luna) is from the same model family as the generator (gpt-5.4-nano). Δ: paired bootstrap difference with its 95% interval. 226 of the questions are unanswerable.

| System | n | Judge score [95% CI] | Correct | Partial | Supported | Judge answerable | Judge unanswerable | Token F1 | F1 answerable |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| P: passages | 4427 | 66.3 [65.1, 67.5] | 50.7 | 31.1 | 89.2 | 68.5 | 24.3 | 27.5 | 27.6 |
| E: passages + 30 facts | 4427 | 66.7 [65.6, 67.8] | 49.9 | 33.5 | 87.8 | 69.0 | 23.5 | 28.0 | 28.2 |
| V1: passages + 10 facts | 4427 | 66.9 [65.8, 68.0] | 50.6 | 32.6 | 87.8 | 69.3 | 21.2 | 28.0 | 28.3 |

| Comparison | n | Δ judge all | Δ judge answerable | Δ judge unanswerable | Δ F1 all | Δ F1 answerable | Δ F1 unanswerable |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| V1 vs P | 4427 | +0.6 [-0.2, 1.5] | +0.8 [-0.0, 1.6] | -3.1 [-8.8, 1.8] | +0.5 [0.1, 0.9] | +0.7 [0.3, 1.0] | -2.6 [-8.2, 2.4] |
| E vs P | 4427 | +0.4 [-0.4, 1.3] | +0.5 [-0.4, 1.3] | -0.9 [-7.1, 5.3] | +0.5 [0.1, 0.9] | +0.6 [0.3, 0.9] | -0.5 [-6.8, 5.5] |
| V1 vs E | 4427 | +0.2 [-0.6, 1.0] | +0.3 [-0.5, 1.1] | -2.2 [-8.4, 3.1] | -0.0 [-0.4, 0.4] | +0.1 [-0.2, 0.4] | -2.1 [-8.0, 3.1] |
