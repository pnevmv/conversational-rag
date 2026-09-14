# Step 5: phase B checks before the full extraction run

Date: 2026-10-03 · Branch: `kg/closed-schema-extraction` · Model: `gpt-5.4-nano-smirnov`, temperature 0, strict JSON schema

This report covers the changes decided after pilot 2 and the four pre-run checks on the same 8 pilot documents: prompt tests, stability, annotation sheets and entity resolution. Nothing extracted by the LLM has been written to Neo4j. **Waiting on:** your annotation of `annotation_sample.csv` before deciding on the full run.

## 1. Changes since pilot 2

| Decision | Implementation |
|---|---|
| 1. Two extra domain → range pairs | `extra_pairs` in `src/kg/schema.py`: Organization -AVAILABLE_AT-> ContactPoint, Requirement -REQUIRES-> Document. These are exact pairs, not new source types, so Organization -AVAILABLE_AT-> Organization stays invalid. The rule check is `is_valid_triple()` |
| 2. Drop type-rule violations at load | Raw output keeps every relation with a `schema_valid` flag. `loadable_relations()` is the load-time filter. Violation rate: §2 |
| 3. Service kinds | Added `appeal`, `insurance`, `online_tool`. Service "other" fell from 41% to 31% |
| 4. Short sections and repeated texts | `src/kg/planning.py`, see the table below |
| 5. Chunking | Units over 1,500 characters are split at sentence boundaries into roughly equal chunks, with the 15-entity cap applied per call. Evidence is checked against the whole section, and every mention keeps its `section_id` |
| 6. Entity resolution | `src/kg/resolve.py`, §6 |
| `alias` field | Optional nullable field. The model puts the full name in `name` and the abbreviation in `alias` |

Corpus plan for the full run:

| | Sections | Note |
|---|---:|---|
| Corpus | 4,114 | |
| `is_boilerplate`, skipped | 300 | Text occurs in 10 or more documents. **All of these are also under 40 characters** (megamenu widgets, "Related PDFs:", "yes or no survey:") |
| Short (under 40 characters), skipped | 262 | |
| Extracted | 3,552 | 3,194 distinct texts; 306 of them occur in 2 or more sections |
| **LLM calls** | **3,542** | 3,194 units + 348 extra calls from chunking 238 long units |

The 10-document threshold catches no long footer. The most repeated long text, a VA "What if I need help?" block, occurs in 7 documents, and the VA "Follow us" social-media footer in 6. Those are therefore extracted once and attached to every occurrence, not skipped. Lowering the threshold to 5 documents would skip about 15 such footer texts.

`Section.is_boilerplate` is in Neo4j: 300 sections. Counts are otherwise unchanged, with 37 sections `is_table`.

## 2. Re-extraction of the 8 pilot documents

Of the 90 sections, 27 were skipped (17 short, 10 boilerplate). The other 63 form 63 units, 3 of them chunked, for 67 LLM calls. There were no errors.

| | Pilot 2 | Pilot 3 |
|---|---:|---:|
| Entities / relations | 511 / 368 | 508 / 393 |
| Relations violating the type rules (rules as now) | 31 (8.4%) | **57 (14.5%)**, dropped at load: **336 loadable** |
| Sections hitting the 15-entity cap | 8 | 4 |
| CamelCase names | 7 | 7 |
| Entities with an `alias` | — | 17 |
| Evidence exact / near-verbatim / not found | 851 / 0 / 28 | 871 / 14 / 16 |
| Quotes containing "…" | 0 | 15 (one loan enumeration) |
| Self-loops (removed by post-processing) | 0 | 8 |
| `value` fill: TimeLimit / ContactPoint / Amount | 37/37 · 32/34 · 12/18 | 35/35 · 25/37 · 10/18 |

**Violation rate.** 57 of 393 relations (14.5%) break the domain → range rules and are not loaded. No single pattern dominates; the most common are:

| Pattern | n |
|---|---:|
| Requirement REQUIRES Requirement | 5 |
| Outcome PART_OF Service | 5 |
| Service / Organization AVAILABLE_AT Document | 6 |
| Organization HAS_TIME_LIMIT TimeLimit | 3 |

Pilot 2's output scores 8.4% under the same rules. The difference is in line with the run-to-run variation measured in §4, rather than a systematic prompt effect.

**ContactPoint `value` regression.** The fill rate fell from 32/34 to 25/37, most likely because of the new clause allowing a null value "when the text gives no value". It could be tightened for ContactPoint only.

## 3. Prompt regression tests

`tests/test_kg_extraction.py` has 15 pytest cases: 12 pass and 3 are strict `xfail`. They read the cached raw model output and never call the API; they skip if the cache is missing. `pytest` was added to `requirements.txt`. The full suite gives 76 passed and 3 xfailed.

| Known error (pilot 1) | Test | Result |
|---|---|---|
| Reversed REQUIRES (learner permit) | road test REQUIRES supervised driving practice, never the reverse | pass |
| Reversed REQUIRES (women's health) | no Requirement as a REQUIRES source | pass |
| Malformed `DisabilityReviewRequirement -REQUIRES-> CaseReview` | Requirement sources only point to Documents | pass |
| Self-loops (VA welcome kit) | none in the raw output for that section | pass |
| EXEMPTS instead of EXEMPT_FROM (fee table) | exempt party → tax/fee direction | **xfail**: the name is fixed, but the model writes `use taxes -EXEMPT_FROM-> Medallion taxis …`, still reversed |
| Row-level enumeration (fee table) | at most 2 registration-class entities | pass |
| CamelCase names | at most 2% | pass (1.4%) |
| Self-loops overall | at most 1% of raw relations | **xfail**: 10/503 (2.0%), removed in post-processing |
| Stitched evidence | no "…" | **xfail**: 15 quotes from one loan enumeration |
| Evidence verbatim | at least 90%, ignoring spacing | pass |
| Alias | MAGI captured for "modified adjusted gross income (MAGI)" | pass |
| TimeLimit value | at least 95% filled | pass |
| Post-processing (deterministic) | drops self-loops and dangling relations; ALTERNATIVE_TO direction is canonical; chunks end at sentence boundaries | 3 × pass |

## 4. Stability (two independent runs)

Run 2 used a separate cache (`experiments/cache/kg_extract_run2`), so the model was called twice at temperature 0. Comparison over the 63 extracted sections, with lightly normalised names, from `pilot3_stability.json`:

| | Run 1 | Run 2 | Shared | Jaccard | Run 1 found by run 2 |
|---|---:|---:|---:|---:|---:|
| Entities (name, type) | 506 | 513 | 378 | 0.59 | 74.7% |
| Loadable triples | 336 | 322 | 162 | **0.33** | **48.2%** |
| Endpoint pairs (relation label ignored) | 336 | 321 | 172 | 0.35 | 51.2% |

**Temperature 0 is far from deterministic.** About a quarter of the entities and half of the triples differ between runs:
- **Entity granularity** varies, e.g. "payment and all required documents" as one entity in one run and two in the other.
- **Peripheral entities** (opening hours, cities) appear in one run only.
- **Types differ:** 24 of the 402 names shared by both runs got different types.

Relation-label flips are a small part of this, since ignoring the label raises Jaccard only from 0.33 to 0.35; the runs mostly disagree on which links exist.

**What this means:** a single extraction pass will miss links that a second pass finds. If recall from the annotation turns out low, running the extraction twice and taking the union (about 7,100 calls) is an option.

## 5. Annotation sheets

`python -m src.kg.annotation export` writes:

- **`annotation_sample.csv`:** every loadable triple (140) from 3 documents, one per domain. The documents are "Register a leased vehicle" (DMV, 48), "Appeal A Decision" (SSA, 39) and "VA Housing Assistance" (VA, 53). Columns: `triple_id, section_id, source, source_type, relation, target, target_type, evidence, label, note`. Fill `label` with `correct` or `incorrect`.
- **`annotation_sections.csv`:** the text of all 31 sections of those documents, including skipped ones (`extracted = no`), for finding missing triples.
- **`annotation_missing.csv`:** an empty template. Add each missing triple as a row, using schema relation and type names; rows the schema doesn't allow are reported and excluded.

`python -m src.kg.annotation score` computes precision (correct / labelled), recall (correct / (correct + missing)) and F1 per relation type and per entity type. A triple counts for both of its endpoint types. The output goes to `annotation_scores.json`. The scorer was checked on a throwaway copy with fake labels; the real sheets are blank.

## 6. Entity resolution

Implemented in `src/kg/resolve.py`, as approved:
- **Blocking:** Service, Requirement, Role and Outcome within their domain; the other types also across domains.
- **Rule matches:** normalised-name groups, plus the alias, acronym and form-number rules.
- **Scoring:** bge-small cosine plus graph signals (+0.02 for the same document, +0.03 per shared neighbour, at most +0.06).
- **Type conflicts:** majority vote over mentions.

**Threshold calibration** (`python -m src.kg.resolve calibrate`, output in `er_calibration.json` and `er_calibration_pairs.csv`). The LLM judged all 455 non-rule pairs scoring ≥ 0.75 and a random 100 of those scoring 0.65–0.75:

| Score | Pairs | LLM: same | Rate |
|---|---:|---:|---:|
| 0.65–0.70 | 66 | 0 | 0.00 |
| 0.70–0.75 | 34 | 1 | 0.03 |
| 0.75–0.80 | 199 | 17 | 0.09 |
| 0.80–0.85 | 117 | 12 | 0.10 |
| 0.85–0.88 | 43 | 9 | 0.21 |
| 0.88–0.90 | 29 | 9 | 0.31 |
| 0.90–0.93 | 27 | 9 | 0.33 |
| 0.93–0.95 | 21 | 12 | 0.57 |
| 0.95–1.00 | 19 | 10 | 0.53 |

**Thresholds chosen:**

- **Lower = 0.75.** Below it, 1 of 100 sampled pairs is a match.
- **Upper: disabled.** Even at 0.95 and above, only about half the pairs are the same entity. The rejected ones are near-identical siblings that embeddings can't separate: Subsidized vs Unsubsidized loans, Medical vs Non-Medical hearings, FFEL PLUS vs FFEL Consolidation. So **only rule matches merge without the LLM**; every other candidate scoring at least 0.75 goes to the LLM.

**Safeguards added after the first pilot run** (which produced chained clusters such as "VA direct deposit" ↔ "contact VA", or 10 years ↔ 10–30 years):

1. **Cannot-link constraints.** Two clusters are not merged if any pair across them was rejected by the LLM. This blocked 14 merges.
2. **Value conflicts.** Amount, TimeLimit or ContactPoint groups whose stated values differ are rejected without an LLM call (57 pairs).
3. **Abbreviation-only aliases.** An alias counts as merge evidence only if it looks like an abbreviation and is unique in its block. The model sometimes fills `alias` with a category label, e.g. "Sales Tax Form" on three different forms, which wrongly merged them.
4. **Top-5 candidates per name group.** This loses 1 of 78 merges on the pilot and bounds the full-corpus LLM cost at about 5 calls per name group. At the pilot's rate of about 0.9 judge calls per group, the full corpus would need roughly 15–20k calls.

**Pilot result** (`python -m src.kg.resolve run`): 508 mentions → 423 name groups → **373 entities**.

- **Type conflicts:** 15 resolved by majority vote.
- **Candidate pairs:** 431. 3 form-number rule matches (IRP-6 variants) merged automatically, 57 were rejected for differing values, and 371 went to the LLM (67 confirmed, 304 rejected).
- **Merges:** 56 applied; 14 blocked by cannot-link.
- **Alias rule:** it fired 0 times. Abbreviations in this sample rarely appear on their own elsewhere.

Files for your review:
- **`er_pilot_clusters.csv`:** the **47 clusters** that merge differently written names, with empty `label` and `note` columns.
- **`er_pilot_pairs.csv`:** every candidate pair with its score, band and LLM verdict.
- **`er_pilot_mentions.jsonl`:** the mention → entity mapping for loading.

Visible remaining errors come from the LLM accepting related-but-different pairs: "Graduated Repayment Plan" ↔ "monthly payments", "Change your VA direct deposit information" ↔ "change your address on file with VA", "appeal" ↔ "Request a Hearing for a Non-Medical Determination".

## 7. Decisions after annotation

1. **Full extraction run (3,542 calls):** go or no-go, depending on the precision in `annotation_scores.json`.
2. **Recall vs stability:** if recall is low, run the extraction twice and take the union (§4)?
3. **Boilerplate threshold:** keep 10 documents (no long text is skipped), or lower it to 5 to skip the VA footers?
4. **ER judge strictness:** depending on your cluster labels, tighten the judge prompt (it accepts related-but-different services), or require two confirmations for Service merges.
5. **ContactPoint `value`:** make it mandatory again (regression from 32/34 to 25/37)?
