# Extraction prompt v1 vs v2 (3 annotated pilot documents)

Paired section bootstrap, B = 2,000, 95% percentile CIs in brackets. Recall is against the same 114 gold triples for both versions.

| | v1 | v2 | v2 − v1 |
|---|---|---|---|
| Precision | 53.6 [40.9, 67.4] | 45.5 [31.2, 65.7] | -8.0 [-25.4, +14.7] |
| Recall | 65.8 [53.6, 79.8] | 32.5 [19.0, 48.2] | -33.3 [-51.4, -13.1] |
| F1 | 59.1 [48.0, 70.7] | 37.9 [25.1, 53.2] | -21.2 [-35.7, -3.2] |
| Labelled triples (correct) | 140 (75) | 123 (56) | |
| Gold facts found (of 114) | 75 | 37 | |
| Correct triples outside the gold set | 0 | 18 | |

## By relation

| Relation | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 | labelled v1 / v2 | gold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALTERNATIVE_TO | 0.0 | 37.5 | 0.0 | 100.0 | 0.0 | 54.5 | 2 / 8 | 3 |
| APPLIES_TO | 53.8 | 73.3 | 77.8 | 22.2 | 63.6 | 34.1 | 26 / 15 | 18 |
| AVAILABLE_AT | 57.9 | 28.6 | 55.0 | 5.0 | 56.4 | 8.5 | 19 / 7 | 20 |
| EXEMPT_FROM | — | 0.0 | — | — | — | — | 0 / 1 | 0 |
| HAS_TIME_LIMIT | 55.6 | 40.0 | 100.0 | 20.0 | 71.4 | 26.7 | 9 / 5 | 5 |
| LEADS_TO | 50.0 | 36.4 | 77.8 | 33.3 | 60.9 | 34.8 | 14 / 11 | 9 |
| PART_OF | 0.0 | 28.6 | 0.0 | 0.0 | 0.0 | 0.0 | 7 / 7 | 7 |
| PROVIDED_BY | 75.0 | 36.4 | 66.7 | 44.4 | 70.6 | 40.0 | 8 / 11 | 9 |
| REQUIRES | 58.2 | 48.3 | 74.4 | 48.8 | 65.3 | 48.6 | 55 / 58 | 43 |

## By document

| Document | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 |
|---|---|---|---|---|---|---|
| DMV leased vehicle | 43.8 [0.0, 100.0] | 51.0 [22.2, 100.0] | 56.8 [36.4, 80.0] | 48.6 [28.6, 81.8] | 49.4 [22.7, 61.5] | 49.8 [25.0, 90.0] |
| SSA appeal | 43.6 [25.6, 60.4] | 28.6 [9.4, 53.6] | 60.7 [31.2, 100.0] | 32.1 [10.5, 71.4] | 50.7 [29.0, 73.2] | 30.3 [10.2, 59.0] |
| VA housing | 69.8 [49.1, 93.0] | 53.8 [38.5, 83.3] | 75.5 [59.1, 91.9] | 20.4 [6.1, 37.7] | 72.5 [55.4, 89.7] | 29.6 [10.8, 46.2] |

## v2 precision by run agreement (run-1 triples)

| | Correct / labelled | Precision (Wilson 95% CI) |
|---|---:|---|
| both runs | 37 / 61 | 60.7 [48.1, 71.9] |
| run1 only | 19 / 62 | 30.6 [20.6, 43.0] |

## Recall variants and the two-run intersection

The fixed gold set (114) was built from v1's output plus the facts v1 missed, so it favours v1. Pooled: gold extended with v2's 18 correct triples outside it (132 facts). No social: without the 5 social-media links the KG layer drops by design.

| | Precision | Recall (fixed 114) | Recall (fixed, no social) | Recall (pooled) | Recall (pooled, no social) |
|---|---:|---:|---:|---:|---:|
| v1 | 53.6 | 65.8 | 64.2 | 56.8 | 55.1 |
| v2 | 45.5 | 32.5 | 33.9 | 41.7 | 43.3 |
| v2 intersection | 60.7 | 21.9 | 22.9 | 28.0 | 29.1 |
