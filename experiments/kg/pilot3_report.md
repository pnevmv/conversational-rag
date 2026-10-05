# Step 5: checks before the full extraction run (pilot 3 and 4)

Model: `gpt-5.4-nano`, temperature 0, strict JSON schema. Same 8 pilot documents as pilot 2.

This report collects the changes made after pilot 2 and the checks I ran before the full extraction: prompt regression tests, run-to-run stability, the annotation sheets and entity resolution. Sections 8-10 are follow-ups: what the deployment allows for sampling, a cheaper batched judge for entity resolution, and a rule for ContactPoint values. At this point nothing extracted by the LLM had been written to Neo4j yet.

## 1. Changes since pilot 2

* Two extra domain -> range pairs in `src/kg/schema.py` (`extra_pairs`): Organization -AVAILABLE_AT-> ContactPoint and Requirement -REQUIRES-> Document. They are exact pairs, so e.g. Organization -AVAILABLE_AT-> Organization is still invalid. The check is `is_valid_triple()`.
* Relations that break the type rules are kept in the raw output with a `schema_valid` flag and dropped at load time by `loadable_relations()`.
* New Service kinds `appeal`, `insurance` and `online_tool`; Service "other" went from 41% to 31%.
* Short and repeated sections are handled in `src/kg/planning.py` (table below).
* Units longer than 1,500 characters are split at sentence boundaries into roughly equal chunks, with the 15-entity cap per call. Evidence is still checked against the whole section and every mention keeps its `section_id`.
* Entity resolution in `src/kg/resolve.py` (section 6).
* An optional `alias` field: the model puts the full name in `name` and the abbreviation in `alias`.

Plan for the full corpus:

| | Sections | Note |
| :--- | ---: | :--- |
| Corpus | 4,114 | |
| Boilerplate, skipped | 300 | text in 10 or more documents; all of them are also shorter than 40 characters (menu widgets, "Related PDFs:", "yes or no survey:") |
| Short (< 40 characters), skipped | 262 | |
| Extracted | 3,552 | 3,194 distinct texts, 306 of them in 2 or more sections |
| LLM calls | 3,542 | 3,194 units + 348 extra calls from chunking 238 long units |

The 10-document threshold doesn't catch any long footer. The most repeated long text, a VA "What if I need help?" block, is in 7 documents and the VA "Follow us" footer in 6, so they are extracted once and attached to every occurrence instead of being skipped. A threshold of 5 documents would skip about 15 of these footers. `Section.is_boilerplate` is set on 300 sections in Neo4j; 37 sections are `is_table`.

## 2. Re-extraction of the 8 pilot documents

Of the 90 sections, 27 were skipped (17 short, 10 boilerplate). The other 63 make 63 units, 3 of them chunked, for 67 LLM calls without errors.

| | Pilot 2 | Pilot 3 |
| :--- | :---: | :---: |
| Entities / relations | 511 / 368 | 508 / 393 |
| Relations breaking the type rules (current rules) | 31 (8.4%) | 57 (14.5%), so 336 loadable |
| Sections hitting the 15-entity cap | 8 | 4 |
| CamelCase names | 7 | 7 |
| Entities with an alias | - | 17 |
| Evidence exact / near-verbatim / not found | 851 / 0 / 28 | 871 / 14 / 16 |
| Quotes containing "..." | 0 | 15 (one loan enumeration) |
| Self-loops (removed in post-processing) | 0 | 8 |
| Value filled: TimeLimit / ContactPoint / Amount | 37/37, 32/34, 12/18 | 35/35, 25/37, 10/18 |

57 of the 393 relations (14.5%) break the type rules and are not loaded. No single pattern dominates: Service/Organization AVAILABLE_AT Document 6, Requirement REQUIRES Requirement 5, Outcome PART_OF Service 5, Organization HAS_TIME_LIMIT TimeLimit 3. Pilot 2 gives 8.4% under the same rules; the difference is within the run-to-run variation of section 4 rather than a prompt effect.

The ContactPoint value fill dropped from 32/34 to 25/37, probably because of the new clause that allows a null value "when the text gives no value". Section 10 looks at this.

## 3. Prompt regression tests

`tests/test_kg_extraction.py` has 15 cases (12 pass, 3 strict xfail). They read the cached model output and never call the API, and they skip if the cache is missing.

| Known error from pilot 1 | Test | Result |
| :--- | :--- | :--- |
| Reversed REQUIRES (learner permit) | road test REQUIRES supervised driving practice, never the reverse | pass |
| Reversed REQUIRES (women's health) | no Requirement as REQUIRES source | pass |
| `DisabilityReviewRequirement -REQUIRES-> CaseReview` | Requirement sources only point to Documents | pass |
| Self-loops (VA welcome kit) | none in that section's raw output | pass |
| EXEMPTS instead of EXEMPT_FROM (fee table) | exempt party -> tax/fee direction | xfail: the name is fixed but the model writes `use taxes -EXEMPT_FROM-> Medallion taxis ...`, still reversed |
| Row-level enumeration (fee table) | at most 2 registration-class entities | pass |
| CamelCase names | at most 2% | pass (1.4%) |
| Self-loops overall | at most 1% of raw relations | xfail: 10/503 (2.0%), removed in post-processing |
| Stitched evidence | no "..." | xfail: 15 quotes from one loan enumeration |
| Evidence verbatim | at least 90%, ignoring spacing | pass |
| Alias | MAGI captured for "modified adjusted gross income (MAGI)" | pass |
| TimeLimit value | at least 95% filled | pass |
| Post-processing | drops self-loops and dangling relations, canonical ALTERNATIVE_TO direction, chunks end at sentence boundaries | 3 x pass |

## 4. Stability (two independent runs)

Run 2 used a separate cache (`experiments/cache/kg_extract_run2`), so the model was called twice at temperature 0. Over the 63 extracted sections, with lightly normalised names (`pilot3_stability.json`):

| | Run 1 | Run 2 | Shared | Jaccard | Run 1 found by run 2 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Entities (name, type) | 506 | 513 | 378 | 0.59 | 74.7% |
| Loadable triples | 336 | 322 | 162 | 0.33 | 48.2% |
| Endpoint pairs (relation ignored) | 336 | 321 | 172 | 0.35 | 51.2% |

Temperature 0 is far from deterministic: about a quarter of the entities and half of the triples differ. Granularity changes ("payment and all required documents" is one entity in one run and two in the other), peripheral entities like opening hours or cities appear only once, and 24 of the 402 names shared by both runs got a different type. Relation labels are a small part of it (ignoring the label only moves Jaccard from 0.33 to 0.35); the runs mostly disagree on which links exist.

So a single pass will miss links that a second pass finds. If recall turned out low, extracting twice and taking the union (about 7,100 calls) would be an option.

## 5. Annotation sheets

`python -m src.kg.annotation export` writes:

* `annotation_sample.csv`: every loadable triple (140) from 3 documents, one per domain: "Register a leased vehicle" (DMV, 48), "Appeal A Decision" (SSA, 39) and "VA Housing Assistance" (VA, 53), with empty `label` and `note` columns;
* `annotation_sections.csv`: the text of all 31 sections of those documents, including skipped ones, to look for missing triples;
* `annotation_missing.csv`: an empty template for the missing triples, using schema names.

`python -m src.kg.annotation score` computes precision (correct / labelled), recall (correct / (correct + missing)) and F1 per relation and per entity type, into `annotation_scores.json`. I checked the scorer on a copy with fake labels first.

## 6. Entity resolution

`src/kg/resolve.py` blocks Service, Requirement, Role and Outcome by domain and the other types also across domains. Names that normalise to the same key are grouped, and the alias, acronym and form-number rules merge directly. Other pairs are scored by the bge-small cosine plus small graph bonuses (+0.02 for the same document, +0.03 per shared neighbour, at most +0.06). Type conflicts are decided by majority vote.

To calibrate the thresholds (`python -m src.kg.resolve calibrate`, `er_calibration.json`), the LLM judged all 455 non-rule pairs scoring at least 0.75 and a random 100 between 0.65 and 0.75:

| Score | Pairs | Same (LLM) | Rate |
| :--- | :---: | :---: | :---: |
| 0.65-0.70 | 66 | 0 | 0.00 |
| 0.70-0.75 | 34 | 1 | 0.03 |
| 0.75-0.80 | 199 | 17 | 0.09 |
| 0.80-0.85 | 117 | 12 | 0.10 |
| 0.85-0.88 | 43 | 9 | 0.21 |
| 0.88-0.90 | 29 | 9 | 0.31 |
| 0.90-0.93 | 27 | 9 | 0.33 |
| 0.93-0.95 | 21 | 12 | 0.57 |
| 0.95-1.00 | 19 | 10 | 0.53 |

I set the lower threshold to 0.75 (below it only 1 of 100 sampled pairs is a match) and disabled the upper one: even above 0.95 only about half of the pairs are the same entity. The rejected ones are near-identical siblings that embeddings can't tell apart, like Subsidized vs Unsubsidized loans, Medical vs Non-Medical hearings, or FFEL PLUS vs FFEL Consolidation. So only rule matches merge without asking the LLM.

The first pilot run produced chained clusters ("VA direct deposit" with "contact VA", "10 years" with "10-30 years"), so I added some safeguards:

1. Cannot-link: two clusters are not merged if the LLM rejected any pair across them (14 merges blocked).
2. Value conflicts: Amount, TimeLimit or ContactPoint groups with different values are rejected without an LLM call (57 pairs).
3. An alias counts as evidence only if it looks like an abbreviation and is unique in its block. The model sometimes puts a category in `alias` (e.g. "Sales Tax Form" on three different forms), which merged them wrongly.
4. Only the top-5 candidates per name group go to the LLM. This loses 1 of 78 merges on the pilot. My first cost estimate from the pilot rate (15-20k calls) was wrong: full-corpus blocks are about 50 times denser, so almost every group reaches 5 candidates, i.e. about 66k pairwise calls or 21k batched ones (section 9).

Pilot result (`python -m src.kg.resolve run`): 508 mentions -> 423 name groups -> 373 entities. 15 type conflicts were resolved by majority. Of 431 candidate pairs, 3 were merged by the form-number rule (IRP-6 variants), 57 rejected for different values and 371 sent to the LLM (67 confirmed, 304 rejected); 56 merges were applied and 14 blocked by cannot-link. The alias rule never fired, since abbreviations in this sample rarely appear on their own elsewhere.

The 47 clusters that merge differently written names are in `er_pilot_clusters.csv` for labelling, every pair with its score and verdict in `er_pilot_pairs.csv`, and the mention -> entity mapping in `er_pilot_mentions.jsonl`. The visible errors are related-but-different pairs accepted by the LLM: "Graduated Repayment Plan" with "monthly payments", "Change your VA direct deposit information" with "change your address on file with VA", "appeal" with "Request a Hearing for a Non-Medical Determination".

## 7. Open questions at this point

* Whether to run the full extraction (3,542 calls), depending on the precision from the annotation.
* Whether to extract twice and take the union (recall) or the intersection (precision).
* Boilerplate threshold: 10 documents (no long text skipped) or 5 (skips the VA footers).
* Whether the ER judge should be stricter for Services, depending on the cluster labels.
* Whether to make the ContactPoint value mandatory again.

(In the end: single run with prompt v2.1, batched judge with threshold 0.80, ContactPoint rule as in section 10, boilerplate threshold unchanged. See `full_build_report.md`.)

## 8. Sampling parameters and stability

What the deployment (`gpt-5.4-nano-2026-03-17`, a reasoning model) accepts:

* `seed`: not supported (400 "Unknown parameter");
* `reasoning.effort`: none, low, medium, high, xhigh; the default is none, with 0 reasoning tokens;
* `temperature`: only accepted with effort none;
* `top_p`: accepted.

To see which setting is most deterministic, I extracted 4 pilot sections 5 times per configuration and compared the repeats by mean pairwise triple Jaccard:

| Configuration | Mean triple Jaccard | Identical repeats |
| :--- | :---: | :---: |
| temperature 0, effort none (previous setting) | 0.34 | 1/40 |
| temperature 0 + top_p 0 | 0.27 | 0/40 |
| top_p 0 only | 0.12 | 0/40 |
| effort low (no temperature) | 0.17 | 0/40 |
| effort medium (no temperature) | 0.24 | 0/40 |

Nothing makes the deployment deterministic; even identical requests at temperature 0 give different outputs. The existing setting is the best one, so it is now pinned explicitly (`CALL_PARAMS = {"reasoning": {"effort": "none"}, "temperature": 0}` in `extract_closed.py`) and is part of the cache key, so a change of the deployment default can't silently change the behaviour.

Re-running the pilot twice with the pinned settings and the ContactPoint rule of section 10 (pilot 4, `pilot4_stability.json`):

| Normalised names, loadable triples | Pilot 3 | Pilot 4 |
| :--- | :---: | :---: |
| Entity Jaccard | 0.59 | 0.57 |
| Triple Jaccard | 0.33 | 0.28 |
| Run 1 triples found by run 2 | 48.2% | 44.3% |
| Endpoint-pair Jaccard | 0.35 | 0.32 |

The overlap is the same within noise, so the variation comes from the deployment and not from the settings. The remaining options are aggregating several runs or using another model.

Other pilot 4 numbers (run 1, `pilot4_stats.json`): 509 entities and 372 relations, 316 loadable (56 rule violations, 15.1%), 4 cap hits, 6 CamelCase names, 15 aliases, 96.0% exact evidence, 1 quote with "...", 7 self-loops removed. Dangling endpoints (relations naming an entity that wasn't extracted) went up to 17 from 4; they are dropped in post-processing.

`python -m src.kg.annotation stability` writes `annotation_stability.csv`, marking which annotated triples (pilot 3 run 1) were also found by pilot 3 run 2, which has the same prompt and settings. 49 of the 140 (35%) were. `annotation score` then reports precision separately for "both runs" and "run 1 only"; if the first is clearly higher, keeping the intersection of two runs is a way to raise precision (about 7,100 calls).

## 9. Batched confirmation for entity resolution

`python -m src.kg.resolve run` now batches by default: one call gets a query name group (name, type, evidence, pages) and up to 5 candidate groups, and returns one decision per candidate, with a `difference` field filled before `same`. Groups with the most pending candidates go first, and a pair already judged from one side is not asked again. The safeguards from section 6 are unchanged. `--pairwise` gives the old judge; the batched outputs are in `er_pilot_batched*_*.csv`.

All prompt variants were measured on the same 371 pilot pairs against the pairwise verdicts:

| Variant | Calls | "Same" | Agreement with pairwise |
| :--- | :---: | :---: | :---: |
| Pairwise (reference) | 371 | 67 (18%) | - |
| Batch v1: returns the list of matching candidates | 162 | 153 (41%) | 0.69 |
| Batch v2: `difference` + `same` per candidate, "most candidates are NOT the same" | 162 | 35 (9%) | 0.85 |
| Batch v3 (kept): `difference` + `same`, spelling variants ARE the same | 162 | 62 (17%) | 0.85 |

v1 merged exactly the siblings the pairwise judge rejects (Subsidized vs Unsubsidized, FFEL PLUS vs FFEL Consolidation), v2 overcorrected and lost real merges (the NY State Insurance ID card variants), and v3 has the same acceptance rate as pairwise. The pairwise judge agrees with itself on 98 of 100 re-asked pairs, so the 15% disagreement of v3 is a real difference and not noise. Looking at the disagreements, they go both ways and are about equally often right and wrong: batched merges VA direct home loan with VA home loan (wrong) but also disability compensation with VA disability compensation (right).

Match rate by similarity bin:

| Score | Pairwise: pairs / same / rate | Batched v3: pairs / same / rate |
| :--- | :---: | :---: |
| 0.75-0.80 | 199 / 17 / 0.09 | 157 / 12 / 0.08 |
| 0.80-0.85 | 117 / 12 / 0.10 | 91 / 11 / 0.12 |
| 0.85-0.90 | 72 / 18 / 0.25 | 65 / 15 / 0.23 |
| 0.90-0.95 | 48 / 21 / 0.44 | 40 / 14 / 0.35 |
| >= 0.95 | 19 / 10 / 0.53 | 18 / 10 / 0.56 |

Effect of the lower threshold on the pairwise judgments:

| Lower threshold | Pairs to judge | "Same" verdicts kept (of 78) |
| :--- | :---: | :---: |
| 0.75 | 455 | 78 |
| 0.80 | 256 (-44%) | 61 |
| 0.85 | 139 | 49 |
| 0.90 | 67 | 31 |

Reading the 17 "same" verdicts between 0.75 and 0.80 by hand, only about 2 are real matches (the Schedule A/C IRP-6 variants, and maybe "hearing" with "Hearing by an administrative law judge"); the rest are wrong merges like "mail" with "phone", "housing grant" with "Veterans Housing Assistance" or "Room 136" with "Room 1366". Between 0.80 and 0.85 about 4 of 12 look right. So I raised the lower threshold to 0.80 (now the default): it removes about 44% of the judge work and mostly false merges, while 0.85 would start losing real ones.

Pilot ER with the new defaults (batched v3, threshold 0.80): 508 mentions -> 423 name groups -> 382 entities. Of 259 candidate pairs, 3 were rule merges, 42 value conflicts and 214 were judged in 111 calls (52 confirmed, 11 blocked by cannot-link); 42 clusters merge differently written names. The pairwise run at 0.75 needed 371 calls for 373 entities.

To estimate the full-corpus cost (`python -m src.kg.resolve estimate`, `er_full_estimate.json`), each pilot block is scaled by 3,194/63 (about 50.7, giving about 21,400 name groups), candidate edges are drawn at the pilot's within-block rate for pairs above the threshold, top-5 is applied and the batches are counted. At scale 1 the simulation gives 348/167 (T = 0.75) and 204/113 (T = 0.80) pairwise/batched calls, close to the 371/162 and 214/111 measured.

| Lower threshold | Pair rate in pilot | Pairwise calls | Batched calls |
| :--- | :---: | :---: | :---: |
| 0.75 | 6.6% | ~66,700 | ~21,300 |
| 0.80 | 3.6% | ~66,500 | ~21,300 |
| 0.85 | 2.1% | ~66,000 | ~21,200 |
| 0.90 | 1.0% | ~63,000 | ~20,400 |

At corpus scale the threshold hardly changes the cost: the blocks are so large that nearly every group has 5 candidates above any of these thresholds, so the top-5 cap decides. Batching cuts the cost by about two thirds, to roughly one call per name group. The simulation ignores the clustering of real similarity graphs, and the group count is an upper bound because identical names across documents collapse into fewer groups. (The full build eventually needed 9,230 calls.)

## 10. ContactPoint value rule

For a ContactPoint whose evidence contains a phone number, postal address, email or URL, the prompt now requires `value` (a copy of that detail); otherwise it can stay null. `has_contact_detail()` / `find_contact_detail()` in `schema.py` detect the formats used in this corpus (spaced phone numbers like "800 - 827 - 1000", "888-GIBILL", PO boxes, ZIP codes, URLs and domains, emails), but not short relay numbers like "TTY : 711". If the model still leaves the value empty, post-processing fills it from the evidence.

| ContactPoints | Pilot 3 | Pilot 4 run 1 | Pilot 4 run 2 |
| :--- | :---: | :---: | :---: |
| All: value filled | 25/37 | 20/35 | 24/38 |
| Detail in evidence: filled by the model | 17/18 | 16/17 | 17/18 |
| Detail in evidence: filled after post-processing | - | 17/17 | 18/18 |

So the earlier "regression" was not about missing details: when the evidence has one, the model already gave a value about 95% of the time. The one consistent miss is "VA.gov profile", where the domain is the name itself, and the fallback fixes it. The lower overall rate comes from ContactPoints without any detail in their evidence ("VA benefits hotline", "Facebook" with the number in another span), which is correct under the rule.

Two new regression tests check that at least 90% of the detail-bearing ContactPoints have a value in the raw output and 100% after post-processing. The test file now has 17 cases, 13 passing and 4 strict xfail: the fee table direction (still reversed), self-loops (7 of 488 raw relations, 1.4%), one stitched quote, and the fee-table enumeration, since the current run lists all 8 registration classes again. That last one was a false pass before: my check split names on spaces, so "Agricultural (AGR)" didn't match the code "AGR".
