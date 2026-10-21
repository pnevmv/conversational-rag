# Generator models (validation, G2 + abstain(G0))

Only the generator calls change model; rewrites, retrieval, graph facts and contexts are identical. All three models were run fresh on the full split with the same code and usage logging. Δ is the paired bootstrap difference in F1 to the fresh gpt-5.4-nano run on the same questions (questions without an answer from either run left out). The row 'gpt-5.4-nano, reported run' is the cached answers of the system in the reports (no usage recorded); comparing it with the fresh gpt-5.4-nano run shows the run-to-run variation of the same model. Tokens and cost are for the generator calls only (G0 always, G2 when G0 does not abstain); the rewriter stays on gpt-5.4-nano.

Prices (USD per 1M tokens input / cached input / output, Global Standard, Azure Retail Prices API, eastus2, checked 2026-10-21): gpt-5.4-nano 0.2 / 0.02 / 1.25 (5.4 nano Inp / cd Inp / Opt Gl); gpt-5-nano 0.05 / 0.005 / 0.4 (GPT 5 Nano Inpt / cchd Inpt / outpt Glbl); gpt-6-luna 0.1 / 0.01 / 0.5 (6-luna ShortCo Inp / Cd Inp / Opt Std Gl)
Cost uses the cached-input price for the input tokens the API reports as cached; 'no cache' is the same tokens all at the full input price.

## Passages

| Model | n | F1 all | F1 answerable | F1 unanswerable | Δ all vs 5.4-nano | Δ answerable | abstain recall / false abstention | tokens/turn in (cached) / out (reasoning) | tokens/conversation in / out (mean, median, p95) | USD per 1,000 conv. (no cache) |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| gpt-5.4-nano | 4427 | 27.6 | 27.6 | 28.4 | - | - | 27.4 / 5.7 | 2492 (273) / 108 (0) | 16687, 15385, 27287 / 724, 710, 1027 | 3.91 (4.24) |
| gpt-5-nano | 4427 | 27.6 | 26.5 | 46.9 | -0.0 [-0.5, 0.5] | -1.0 [-1.4, -0.6] | 46.0 / 12.5 | 2394 (180) / 1569 (1425) | 16036, 14916, 25650 / 10507, 10185, 15947 | 4.95 (5.00) |
| gpt-6-luna | 4427 | 26.8 | 25.8 | 46.4 | -0.8 [-1.3, -0.2] | -1.8 [-2.2, -1.3] | 45.6 / 17.3 | 2348 (198) / 151 (80) | 15729, 14606, 25703 / 1014, 968, 1724 | 1.96 (2.08) |
| gpt-5.4-nano, reported run | 4427 | 27.5 | 27.6 | 25.0 | -0.1 [-0.5, 0.2] | +0.1 [-0.2, 0.3] | 24.3 / 5.6 | - | - | - |

## Passages + graph facts

| Model | n | F1 all | F1 answerable | F1 unanswerable | Δ all vs 5.4-nano | Δ answerable | abstain recall / false abstention | tokens/turn in (cached) / out (reasoning) | tokens/conversation in / out (mean, median, p95) | USD per 1,000 conv. (no cache) |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| gpt-5.4-nano | 4427 | 28.1 | 28.4 | 23.3 | - | - | 22.6 / 3.9 | 5793 (1113) / 106 (0) | 38798, 37068, 55394 / 708, 693, 989 | 7.30 (8.64) |
| gpt-5-nano | 4427 | 28.1 | 26.8 | 51.9 | -0.0 [-0.6, 0.5] | -1.6 [-2.0, -1.2] | 51.3 / 11.6 | 5532 (477) / 1578 (1435) | 37053, 35320, 54955 / 10571, 10368, 16122 | 5.94 (6.08) |
| gpt-6-luna | 4427 | 27.3 | 26.6 | 41.0 | -0.8 [-1.4, -0.3] | -1.8 [-2.2, -1.4] | 40.3 / 14.2 | 5511 (642) / 176 (102) | 36910, 35198, 54701 / 1176, 1130, 1915 | 3.89 (4.28) |
| gpt-5.4-nano, reported run | 4427 | 28.0 | 28.2 | 24.5 | -0.1 [-0.5, 0.2] | -0.2 [-0.4, 0.1] | 23.5 / 4.6 | - | - | - |
