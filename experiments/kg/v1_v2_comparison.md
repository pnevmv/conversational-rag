# Extraction prompt v1 vs v2 (3 annotated pilot documents)

Paired section bootstrap, B = 2,000, 95% percentile CIs in brackets. Recall is against the same 95 gold triples for both versions.

| | v1 | v2 | v2 − v1 |
|---|---|---|---|
| Precision | 44.3 [32.3, 56.8] | 53.7 [37.9, 69.9] | +9.4 [-7.0, +27.2] |
| Recall | 65.3 [52.1, 79.4] | 43.2 [25.5, 58.0] | -22.1 [-44.4, -2.2] |
| F1 | 52.8 [41.9, 63.4] | 47.8 [31.1, 62.2] | -4.9 [-22.2, +11.4] |
| Labelled triples (correct) | 140 (62) | 123 (66) | |
| Gold facts found (of 95) | 62 | 41 | |
| Correct triples outside the gold set | 0 | 23 | |

## By relation

| Relation | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 | labelled v1 / v2 | gold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALTERNATIVE_TO | 0.0 | 75.0 | 0.0 | 66.7 | 0.0 | 70.6 | 2 / 8 | 3 |
| APPLIES_TO | 46.2 | 66.7 | 80.0 | 53.3 | 58.5 | 59.3 | 26 / 15 | 15 |
| AVAILABLE_AT | 57.9 | 28.6 | 68.8 | 6.2 | 62.9 | 10.3 | 19 / 7 | 16 |
| EXEMPT_FROM | — | 0.0 | — | — | — | — | 0 / 1 | 0 |
| HAS_AMOUNT | — | — | 0.0 | 0.0 | — | — | 0 / 0 | 2 |
| HAS_TIME_LIMIT | 22.2 | 20.0 | 100.0 | 50.0 | 36.4 | 28.6 | 9 / 5 | 2 |
| LEADS_TO | 28.6 | 36.4 | 57.1 | 42.9 | 38.1 | 39.3 | 14 / 11 | 7 |
| PART_OF | 0.0 | 28.6 | 0.0 | 0.0 | 0.0 | 0.0 | 7 / 7 | 4 |
| PROVIDED_BY | 87.5 | 81.8 | 63.6 | 45.5 | 73.7 | 58.4 | 8 / 11 | 11 |
| REQUIRES | 47.3 | 55.2 | 74.3 | 60.0 | 57.8 | 57.5 | 55 / 58 | 35 |

## By document

| Document | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 |
|---|---|---|---|---|---|---|
| DMV leased vehicle | 39.6 [9.1, 100.0] | 73.5 [51.9, 100.0] | 55.9 [36.4, 100.0] | 64.7 [0.0, 81.8] | 46.3 [16.7, 61.5] | 68.8 [0.0, 90.0] |
| SSA appeal | 23.1 [10.9, 37.0] | 25.7 [9.1, 41.9] | 52.9 [26.7, 100.0] | 23.5 [0.0, 69.2] | 32.1 [15.9, 47.8] | 24.6 [0.0, 51.3] |
| VA housing | 64.2 [45.8, 87.5] | 53.8 [31.7, 88.5] | 77.3 [54.5, 92.7] | 34.1 [12.1, 56.9] | 70.1 [53.0, 85.2] | 41.7 [18.4, 65.3] |

## v2 precision by run agreement (run-1 triples)

| | Correct / labelled | Precision (Wilson 95% CI) |
|---|---:|---|
| both runs | 44 / 61 | 72.1 [59.8, 81.8] |
| run1 only | 22 / 62 | 35.5 [24.7, 47.9] |

## Recall variants and the two-run intersection

The fixed gold set (95) was built from v1's output plus the facts v1 missed, so it favours v1. Pooled: gold extended with v2's 23 correct triples outside it (118 facts). No social: without the 5 social-media links the KG layer drops by design.

| | Precision | Recall (fixed 95) | Recall (fixed, no social) | Recall (pooled) | Recall (pooled, no social) |
|---|---:|---:|---:|---:|---:|
| v1 | 44.3 | 65.3 | 63.3 | 52.5 | 50.4 |
| v2 | 53.7 | 43.2 | 45.6 | 54.2 | 56.6 |
| v2 intersection | 72.1 | 32.6 | 34.4 | 35.6 | 37.2 |
