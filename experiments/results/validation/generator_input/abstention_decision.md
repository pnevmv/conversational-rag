# Abstention decisions for the conversational generator (validation)

Generator G2 (whole gold history) in every row; only the decision to abstain changes. Δ is the paired bootstrap difference to G2 + abstain(G0). Tokens per turn: the decision call (if any) plus the G2 call when the decision is to answer; generator tokens are counted from the text (no reasoning tokens), classifier tokens come from the API.

## Step 4 best

Classifier: 2 API errors (counted as yes), 0 answers not yes/no; says no on 21.3% of the turns. Threshold chosen on dev-500: 0.3034 (abstains on 3.1% of the validation turns).

| Decision | F1 all | F1 answerable | F1 unanswerable | Δ all vs G2+abstain(G0) | abstain recall / false abstention | in / out tokens per turn |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| G2 (no decision step) | 27.2 | 28.1 | 10.6 | -0.3 [-0.6, -0.1] | 9.7 / 2.8 | 1415 / 56 |
| G2 + abstain(G0) | 27.5 | 27.6 | 25.0 | - | 24.3 / 5.6 | 2637 / 110 |
| G2 + classifier | 26.2 | 24.8 | 50.7 | -1.3 [-1.8, -0.8] | 50.0 / 20.0 | 2368 / 51 |
| G2 + reranker threshold (t = 0.3034) | 26.9 | 27.5 | 14.5 | -0.6 [-0.9, -0.3] | 13.7 / 5.4 | 1374 / 55 |

## E

Classifier: 2 API errors (counted as yes), 0 answers not yes/no; says no on 18.9% of the turns. Threshold chosen on dev-500: 0.3034 (abstains on 3.1% of the validation turns).

| Decision | F1 all | F1 answerable | F1 unanswerable | Δ all vs G2+abstain(G0) | abstain recall / false abstention | in / out tokens per turn |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| G2 (no decision step) | 27.7 | 28.5 | 12.9 | -0.3 [-0.5, -0.1] | 11.9 / 2.5 | 3219 / 54 |
| G2 + abstain(G0) | 28.0 | 28.2 | 24.5 | - | 23.5 / 4.6 | 6186 / 106 |
| G2 + classifier | 27.0 | 25.7 | 51.2 | -1.0 [-1.4, -0.5] | 50.9 / 17.7 | 5667 / 50 |
| G2 + reranker threshold (t = 0.3034) | 27.4 | 27.9 | 17.3 | -0.6 [-0.9, -0.3] | 16.4 / 5.2 | 3132 / 53 |
