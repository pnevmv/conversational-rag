# Extraction prompt v1 vs v2 (3 annotated pilot documents)

Paired section bootstrap, B = 2,000, 95% percentile CIs in brackets. Recall is against the same 110 gold triples for both versions.

| | v1 | v2 | v2 − v1 |
|---|---|---|---|
| Precision | 51.4 [39.4, 66.4] | 45.5 [31.2, 65.7] | -5.9 [-22.2, +14.9] |
| Recall | 65.5 [52.7, 80.2] | 38.2 [25.6, 52.1] | -27.3 [-44.6, -9.5] |
| F1 | 57.6 [47.0, 70.4] | 41.5 [29.3, 56.4] | -16.1 [-30.7, +0.4] |
| Labelled triples (correct) | 140 (72) | 123 (56) | |
| Gold facts found (of 110) | 72 | 42 | |
| Correct triples outside the gold set | 0 | 11 | |

## By relation

| Relation | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 | labelled v1 / v2 | gold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALTERNATIVE_TO | 0.0 | 37.5 | 0.0 | 100.0 | 0.0 | 54.5 | 2 / 8 | 3 |
| APPLIES_TO | 53.8 | 73.3 | 82.4 | 47.1 | 65.1 | 57.3 | 26 / 15 | 17 |
| AVAILABLE_AT | 57.9 | 28.6 | 55.0 | 5.0 | 56.4 | 8.5 | 19 / 7 | 20 |
| EXEMPT_FROM | — | 0.0 | — | — | — | — | 0 / 1 | 0 |
| HAS_TIME_LIMIT | 55.6 | 40.0 | 100.0 | 40.0 | 71.4 | 40.0 | 9 / 5 | 5 |
| LEADS_TO | 50.0 | 36.4 | 77.8 | 33.3 | 60.9 | 34.8 | 14 / 11 | 9 |
| PART_OF | 0.0 | 28.6 | 0.0 | 0.0 | 0.0 | 0.0 | 7 / 7 | 7 |
| PROVIDED_BY | 75.0 | 36.4 | 66.7 | 44.4 | 70.6 | 40.0 | 8 / 11 | 9 |
| REQUIRES | 52.7 | 48.3 | 72.5 | 52.5 | 61.1 | 50.3 | 55 / 58 | 40 |

## By document

| Document | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 |
|---|---|---|---|---|---|---|
| DMV leased vehicle | 37.5 [0.0, 100.0] | 51.0 [22.2, 100.0] | 52.9 [36.4, 80.0] | 52.9 [33.3, 81.8] | 43.9 [22.7, 61.5] | 52.0 [26.7, 90.0] |
| SSA appeal | 43.6 [25.6, 60.4] | 28.6 [9.4, 53.6] | 60.7 [31.2, 100.0] | 32.1 [10.5, 71.4] | 50.7 [29.0, 73.2] | 30.3 [10.2, 59.0] |
| VA housing | 69.8 [49.1, 93.0] | 53.8 [38.5, 83.3] | 77.1 [61.0, 91.9] | 31.2 [17.0, 46.7] | 73.3 [56.5, 89.7] | 39.5 [25.1, 55.1] |

## v2 precision by run agreement (run-1 triples)

| | Correct / labelled | Precision (Wilson 95% CI) |
|---|---:|---|
| both runs | 37 / 61 | 60.7 [48.1, 71.9] |
| run1 only | 19 / 62 | 30.6 [20.6, 43.0] |

## Recall variants and the two-run intersection

The fixed gold set (110) was built from v1's output plus the facts v1 missed, so it favours v1. Pooled: gold extended with v2's 11 correct triples outside it (121 facts). No social: without the 5 social-media links the KG layer drops by design.

| | Precision | Recall (fixed 110) | Recall (fixed, no social) | Recall (pooled) | Recall (pooled, no social) |
|---|---:|---:|---:|---:|---:|
| v1 | 51.4 | 65.5 | 63.8 | 59.5 | 57.8 |
| v2 | 45.5 | 38.2 | 40.0 | 43.8 | 45.7 |
| v2 intersection | 60.7 | 26.4 | 27.6 | 28.9 | 30.2 |
