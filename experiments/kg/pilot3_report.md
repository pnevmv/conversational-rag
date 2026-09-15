# Step 5: phase B checks before the full extraction run

Date: 2026-10-03 · Branch: `kg/closed-schema-extraction` · Model: `gpt-5.4-nano-smirnov`, temperature 0, strict JSON schema

This report covers the changes decided after pilot 2 and the four pre-run checks on the same 8 pilot documents: prompt tests, stability, annotation sheets and entity resolution. **§8–§10 (added 2026-10-03)** cover the three follow-up fixes: sampling parameters and stability, batched entity resolution, and the ContactPoint `value` rule. Nothing extracted by the LLM has been written to Neo4j. **Waiting on:** your annotation of `annotation_sample.csv` before deciding on the full run.

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
4. **Top-5 candidates per name group.** This loses 1 of 78 merges on the pilot and bounds the full-corpus LLM cost at about 5 calls per name group. ~~At the pilot's rate of about 0.9 judge calls per group, the full corpus would need roughly 15–20k calls.~~ **Corrected in §9:** full-corpus blocks are about 50 times denser, so almost every group reaches 5 candidates. That means about 66k pairwise calls, or about 21k batched calls.

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

## 8. Stability fix: sampling parameters

**What the deployment honours.** Probed directly on `gpt-5.4-nano-smirnov` (`gpt-5.4-nano-2026-03-17`), which is a reasoning model:

| Parameter | Result |
|---|---|
| `seed` | **Not supported** (400 "Unknown parameter") |
| `reasoning.effort` | none, low, medium, high, xhigh (not "minimal"). The default is effort none: 0 reasoning tokens in every call |
| `temperature` | Accepted **only with effort "none"**; any higher effort rejects it ("not supported with this model") |
| `top_p` | Accepted |

**Which setting is most deterministic.** 4 pilot sections, each extracted 5 times per configuration, compared by mean pairwise triple Jaccard between repeats:

| Configuration | Mean triple Jaccard | Identical repeats |
|---|---:|---:|
| temperature 0, effort none (previous setting) | **0.34** | 1/40 |
| temperature 0 + top_p 0 | 0.27 | 0/40 |
| top_p 0 only | 0.12 | 0/40 |
| effort low (temperature not allowed) | 0.17 | 0/40 |
| effort medium (temperature not allowed) | 0.24 | 0/40 |

**No configuration makes the deployment deterministic**; even identical requests at temperature 0 return different outputs. The most deterministic option is the existing one. It is now pinned explicitly (`CALL_PARAMS = {"reasoning": {"effort": "none"}, "temperature": 0}` in `extract_closed.py`), so a change to the deployment's default can't silently change behaviour. The parameters are part of the cache key.

**Re-run** of the pilot twice with the pinned settings, also using the ContactPoint rule of §10 (`pilot4_closed_extraction.jsonl`, `pilot4_closed_extraction_run2.jsonl`, `pilot4_stability.json`):

| Normalised names, loadable triples | Pilot 3 (§4) | Pilot 4 |
|---|---:|---:|
| Entity Jaccard | 0.59 | 0.57 |
| Triple Jaccard | 0.33 | **0.28** |
| Run 1 triples found by run 2 | 48.2% | **44.3%** |
| Endpoint-pair Jaccard | 0.35 | 0.32 |

The overlap is unchanged within noise. Run-to-run variation is a property of the deployment, not of our settings. The remaining levers are aggregation over several runs (union for recall, or intersection / majority for precision) or a different model.

**Other pilot 4 figures** (run 1, `pilot4_stats.json`):

| | Pilot 4 |
|---|---|
| Entities / relations | 509 / 372 |
| Loadable relations | 316 (56 type-rule violations, **15.1%**) |
| Cap hits | 4 |
| CamelCase names | 6 |
| Aliases | 15 |
| Evidence exact | 96.0% |
| Quotes with "…" | 1 |
| Self-loops (removed) | 7 |

Dangling endpoints rose to 17 (from 4). These are relations naming an entity that wasn't extracted, and they are dropped in post-processing.

**Annotation split by stability.** `python -m src.kg.annotation stability` wrote `annotation_stability.csv` (`triple_id, in_run2`). It compares each annotated triple, from pilot 3 run 1, with **pilot 3 run 2**: that run used the same prompt and settings, while pilot 4 changed the prompt. **49 of the 140 annotated triples (35%)** were also found by run 2. `python -m src.kg.annotation score` now also prints precision separately for "both runs" and "run 1 only". This was tested on throwaway copies; your sheets were only read.

If both-run triples turn out clearly more precise, extracting twice and keeping the intersection is a precision lever: about 7,100 calls instead of 3,542.

## 9. Cheaper entity resolution: batched confirmation

**Batching.** `python -m src.kg.resolve run` now batches by default. One call receives a query name group (name, type, evidence, pages) and up to 5 candidate groups. It returns one decision per candidate, with a `difference` field the model fills in before setting `same`. Groups with the most pending candidates are queried first, and a pair judged from one side isn't asked again. All safeguards are kept: cannot-link from rejections, value conflicts, abbreviation-only aliases and top-5 candidates. `--pairwise` reproduces the old judge. Your `er_pilot_clusters.csv` (pairwise, threshold 0.75) is untouched; batched outputs go to `er_pilot_batched*_*.csv`.

**Batch prompt design.** All variants were measured on the same 371 pilot pairs against the pairwise verdicts:

| Variant | Calls | "Same" verdicts | Agreement with pairwise |
|---|---:|---:|---:|
| Pairwise (reference) | 371 | 67 (18%) | — |
| Batch v1: returns a list of matching candidates | 162 | 153 (41%) | 0.69 |
| Batch v2: per-candidate `difference` + `same`, "most candidates are NOT the same" | 162 | 35 (9%) | 0.85 |
| **Batch v3 (kept):** per-candidate `difference` + `same`, spelling variants ARE the same | 162 | **62 (17%)** | **0.85** |

- **v1** merged the very siblings the pairwise judge rejects, e.g. Subsidized vs Unsubsidized loans and FFEL PLUS vs FFEL Consolidation.
- **v2** over-corrected and lost true merges such as the NY State Insurance ID card variants.
- **v3** matches the pairwise acceptance rate.

For reference, the pairwise judge agrees with itself on 98 of 100 pairs re-asked with a fresh cache. **So v3's 15% disagreement is a real behaviour difference, not noise.** The disagreements run both ways and look about equally often right and wrong on inspection:
- **Batched merges that look wrong:** VA direct home loan ↔ VA home loan; register a leased vehicle ↔ register your vehicle.
- **Batched merges that look right:** disability compensation ↔ VA disability compensation; Insurance ID Card ↔ NY State Insurance ID cards.
- **Pairwise-only merges** are similarly mixed.

Your labels on `er_pilot_clusters.csv` can decide which judge to trust, since every decision is listed in `er_pilot_pairs.csv` and `er_pilot_batched075_pairs.csv`.

**Match rate by similarity bin** (all pilot judgments; pairwise from the calibration in §6, batched v3 from the 0.75 run):

| Score | Pairwise: pairs / same / rate | Batched v3: pairs / same / rate |
|---|---:|---:|
| 0.75–0.80 | 199 / 17 / 0.09 | 157 / 12 / 0.08 |
| 0.80–0.85 | 117 / 12 / 0.10 | 91 / 11 / 0.12 |
| 0.85–0.90 | 72 / 18 / 0.25 | 65 / 15 / 0.23 |
| 0.90–0.95 | 48 / 21 / 0.44 | 40 / 14 / 0.35 |
| ≥ 0.95 | 19 / 10 / 0.53 | 18 / 10 / 0.56 |

Effect of the lower threshold on the pairwise judgments:

| Lower threshold | Pairs to judge | "Same" verdicts kept (of 78) |
|---|---:|---:|
| 0.75 | 455 | 78 |
| **0.80** | **256 (−44%)** | **61** |
| 0.85 | 139 | 49 |
| 0.90 | 67 | 31 |

**Proposal: lower threshold = 0.80 (now the default).** Reading the 17 "same" verdicts in 0.75–0.80 by hand, only about 2 are real matches: the Schedule A/C IRP-6 variants, and arguably "hearing" ↔ "Hearing by an administrative law judge". The rest are wrong merges, e.g. "mail" ↔ "phone", "housing grant" ↔ "Veterans Housing Assistance", "Room 136" ↔ "Room 1366". In 0.80–0.85 about 4 of 12 look right. Raising the threshold to 0.80 removes about 44% of the judge workload and mostly false merges; 0.85 would start dropping real ones. This hand reading is indicative; your cluster labels will confirm or correct it.

Pilot ER with the new defaults (batched v3, threshold 0.80, `er_pilot_batched_*`):
- **Result:** 508 mentions → 423 name groups → **382 entities**.
- **Pairs:** 259 candidates; 3 rule merges, 42 value conflicts, 214 judged in **111 calls**.
- **Merges:** 52 confirmed, 11 blocked by cannot-link.
- **Review:** 42 clusters merge differently written names.

The pairwise run at 0.75 needed 371 calls for 373 entities.

**Full-corpus estimate** (`python -m src.kg.resolve estimate`, `er_full_estimate.json`):
- **Method:** each pilot block is scaled by 3,194/63 ≈ 50.7, giving about 21,400 name groups. Candidate edges are drawn at the pilot's pooled within-block rate of pairs scoring ≥ T, top-5 is applied per group, and the batching plan is counted.
- **Check:** at scale 1 the simulation gives 348/167 (T = 0.75) and 204/113 (T = 0.80) pairwise/batched calls, against 371/162 and 214/111 measured.

| Lower threshold | Pair rate in pilot | Pairwise calls | **Batched calls** |
|---|---:|---:|---:|
| 0.75 | 6.6% | ~66,700 | **~21,300** |
| 0.80 | 3.6% | ~66,500 | **~21,300** |
| 0.85 | 2.1% | ~66,000 | **~21,200** |
| 0.90 | 1.0% | ~63,000 | **~20,400** |

**At corpus scale the threshold hardly changes the cost.** Blocks become so large (e.g. thousands of Service groups per domain) that almost every group has at least 5 candidates above any of these thresholds, so the top-5 cap sets the cost. Batching cuts it by about two thirds, to **roughly one call per name group (~21k)**. The threshold still matters for quality: in dense blocks a group's top 5 will mostly be high-similarity pairs.

Two caveats:
- The random-graph model ignores the clustering of real similarity graphs.
- The group count is an upper bound: identical names across documents (DMV, VA, proof of identity) will collapse into fewer groups.

Further reductions would need fewer name groups (e.g. pre-merging exact names across the whole corpus, which the pipeline already does within a block) or top-3 instead of top-5. Neither has been tested.

## 10. ContactPoint `value` rule

- **Prompt:** for a ContactPoint whose evidence contains a phone number, postal address, email or URL, `value` is now **required** (copy that detail). Otherwise it may still be null.
- **Detector:** `has_contact_detail()` / `find_contact_detail()` in `schema.py`. It covers this corpus's formats (spaced phone numbers such as "800 - 827 - 1000", "888-GIBILL", PO boxes, ZIP codes, URLs and domains, emails). It does not catch short relay numbers like "TTY : 711".
- **Post-processing fallback:** if the model still leaves the value empty, the detail found in the evidence is used (`contact_value_from_evidence`).

| ContactPoints | Pilot 3 | Pilot 4 run 1 | Pilot 4 run 2 |
|---|---:|---:|---:|
| All: value filled | 25/37 | 20/35 | 24/38 |
| Detail in evidence: filled by the model | 17/18 | 16/17 | 17/18 |
| Detail in evidence: filled after post-processing | — | **17/17** | **18/18** |

**The earlier "regression" was not about missing contact details.** When the evidence contains one, the model already gave a value about 95% of the time. The one consistent miss is "VA.gov profile", where the domain is the name itself; the fallback fills it. The lower overall fill comes from ContactPoints whose evidence has no detail (e.g. "VA benefits hotline", "Facebook", with the number in another span). That's correct under the rule.

**Regression tests.** Two new cases in `tests/test_kg_extraction.py`:
- raw model output: at least 90% of detail-bearing ContactPoints have a value;
- post-processed output: 100%.

The test file now has 17 cases: 13 pass and 4 are strict `xfail` with current numbers.
- **Fee table direction:** still reversed.
- **Self-loops:** 7 of 488 raw relations (1.4%).
- **Stitched quote:** 1 quote with "…".
- **Fee-table enumeration:** the current run lists all 8 registration classes again.

That last one was previously a false pass: my check split names on spaces, so "Agricultural (AGR)" didn't match the code "AGR". The full suite gives 77 passed and 4 xfailed.

## 11. Updated decisions after annotation

1. **Full extraction run (3,542 calls):** go or no-go on the precision in `annotation_scores.json`.
2. **Run aggregation:** if "both runs" precision clearly exceeds "run 1 only", extract twice and use the intersection (or union, if recall is the problem). About 7,100 calls.
3. **ER judge:** pairwise or batched v3, decided by your labels on `er_pilot_clusters.csv`. Batched: ~21k calls for the full corpus. Pairwise: ~66k.
4. **Lower threshold 0.80** (proposed, now the default) or keep 0.75.
5. Boilerplate threshold: unchanged question from §7.
