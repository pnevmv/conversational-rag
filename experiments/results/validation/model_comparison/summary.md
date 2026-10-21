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

### Answer quality without refusals (answerable questions)

| Model | answered (not abstained) | F1 on them | mean words | F1 on the common subset | Δ vs 5.4-nano (common subset) |
| :--- | ---: | :---: | :---: | :---: | :---: |
| gpt-5.4-nano | 3960 of 4201 | 29.1 | 48.4 | 30.7 | - |
| gpt-5-nano | 3674 of 4201 | 30.1 | 41.1 | 31.0 | +0.4 [-0.1, 0.7] |
| gpt-6-luna | 3474 of 4201 | 30.8 | 34.1 | 31.1 | +0.5 [0.1, 0.9] |

Common subset: the 3326 answerable questions where all three models answered.

### Mixed system: abstention from gpt-5.4-nano G0, answer from another model's G2

Same G2 + abstain(G0) logic; G0 runs on gpt-5.4-nano and G2 on the other model. No new calls were made: the other model's G2 answer is in the cache only where its own G0 did not abstain, so questions where gpt-5.4-nano answers but the other model's G2 was never called are left out (counted below), and every comparison uses the same questions for both systems.

| Answer model | n (left out) | F1 all | F1 answerable | F1 unanswerable | Δ all vs 5.4-nano | Δ answerable | abstain recall / false abstention | USD per 1,000 conv. |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| gpt-5-nano | 4058 (369) | 28.5 | 28.4 | 31.9 | +0.2 [-0.2, 0.5] | +0.2 [-0.2, 0.6] | 30.7 / 6.6 | 4.93 |
| gpt-6-luna | 3922 (505) | 28.7 | 28.5 | 33.8 | +0.0 [-0.4, 0.4] | +0.0 [-0.4, 0.4] | 32.7 / 8.3 | 3.31 |

Cost: G0 on gpt-5.4-nano for every question plus G2 on the other model when G0 answers, from the recorded usage; the left-out G2 calls are counted at the mean G2 cost of that model.

## Passages + graph facts

| Model | n | F1 all | F1 answerable | F1 unanswerable | Δ all vs 5.4-nano | Δ answerable | abstain recall / false abstention | tokens/turn in (cached) / out (reasoning) | tokens/conversation in / out (mean, median, p95) | USD per 1,000 conv. (no cache) |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| gpt-5.4-nano | 4427 | 28.1 | 28.4 | 23.3 | - | - | 22.6 / 3.9 | 5793 (1113) / 106 (0) | 38798, 37068, 55394 / 708, 693, 989 | 7.30 (8.64) |
| gpt-5-nano | 4427 | 28.1 | 26.8 | 51.9 | -0.0 [-0.6, 0.5] | -1.6 [-2.0, -1.2] | 51.3 / 11.6 | 5532 (477) / 1578 (1435) | 37053, 35320, 54955 / 10571, 10368, 16122 | 5.94 (6.08) |
| gpt-6-luna | 4427 | 27.3 | 26.6 | 41.0 | -0.8 [-1.4, -0.3] | -1.8 [-2.2, -1.4] | 40.3 / 14.2 | 5511 (642) / 176 (102) | 36910, 35198, 54701 / 1176, 1130, 1915 | 3.89 (4.28) |
| gpt-5.4-nano, reported run | 4427 | 28.0 | 28.2 | 24.5 | -0.1 [-0.5, 0.2] | -0.2 [-0.4, 0.1] | 23.5 / 4.6 | - | - | - |

### Answer quality without refusals (answerable questions)

| Model | answered (not abstained) | F1 on them | mean words | F1 on the common subset | Δ vs 5.4-nano (common subset) |
| :--- | ---: | :---: | :---: | :---: | :---: |
| gpt-5.4-nano | 4036 of 4201 | 29.5 | 46.4 | 30.8 | - |
| gpt-5-nano | 3712 of 4201 | 30.1 | 40.3 | 30.7 | -0.1 [-0.5, 0.2] |
| gpt-6-luna | 3603 of 4201 | 30.6 | 34.3 | 30.8 | -0.0 [-0.4, 0.4] |

Common subset: the 3443 answerable questions where all three models answered.

### Mixed system: abstention from gpt-5.4-nano G0, answer from another model's G2

Same G2 + abstain(G0) logic; G0 runs on gpt-5.4-nano and G2 on the other model. No new calls were made: the other model's G2 answer is in the cache only where its own G0 did not abstain, so questions where gpt-5.4-nano answers but the other model's G2 was never called are left out (counted below), and every comparison uses the same questions for both systems.

| Answer model | n (left out) | F1 all | F1 answerable | F1 unanswerable | Δ all vs 5.4-nano | Δ answerable | abstain recall / false abstention | USD per 1,000 conv. |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| gpt-5-nano | 4015 (412) | 28.9 | 28.8 | 31.4 | -0.3 [-0.6, 0.1] | -0.3 [-0.7, 0.1] | 30.6 / 4.7 | 7.68 |
| gpt-6-luna | 3990 (437) | 28.8 | 28.9 | 27.1 | -0.3 [-0.7, 0.1] | -0.4 [-0.7, 0.0] | 26.2 / 6.3 | 6.61 |

Cost: G0 on gpt-5.4-nano for every question plus G2 on the other model when G0 answers, from the recorded usage; the left-out G2 calls are counted at the mean G2 cost of that model.

## Prices

All costs are USD list prices from the Azure Retail Prices API (prices.azure.com), Global Standard deployment, region East US 2, checked on 2026-10-21. The deployment type and region of the project's deployments are not confirmed, so the real prices can differ.

Check against the Azure bill of gpt-5.4-nano (EUR 34.56 for 164.62 M input and 11.56 M output tokens over the whole project, i.e. EUR 0.196 per 1 M tokens on average): the same tokens at the list price cost USD 47.37 if no input is cached, and USD 17.74 if all input were cached. The bill (EUR 34.56) lies inside this range; it does not say how much input was cached, and the EUR/USD rate is not applied here, so the bill neither confirms nor contradicts the list price exactly.
