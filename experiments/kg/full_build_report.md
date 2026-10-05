# Step 5: full KG build (prompt v2.1, single run)

Model: `gpt-5.4-nano` (Azure), reasoning effort none, temperature 0. Neo4j scope `full`, run id `full_v21`. The `pilot` scope is still in the database next to it.

The whole corpus was extracted once with prompt v2.1, entities were resolved with the batched judge (generic-vs-specific rule, lower threshold 0.80) and both layers were loaded into Neo4j. After the first build, generic names like "application" or "fee" turned out to be hubs, so a hub guard was added to entity resolution and the graph was rebuilt from the cache (section 6). The numbers below are for the final graph unless stated otherwise: 14,731 entities and 13,277 entity relations.

To reproduce:

```bash
python -m src.kg.extract_closed --all --prompt-version v2.1 --workers 16 \
  --usage-log experiments/kg/full_usage_extract.jsonl --output experiments/kg/full_v21_extraction.jsonl
python -m src.kg.resolve run --input experiments/kg/full_v21_extraction.jsonl --prefix er_full \
  --workers 16 --usage-log experiments/kg/full_usage_er.jsonl
python -m src.kg.load_neo4j --scope full --run-id full_v21 \
  --extraction experiments/kg/full_v21_extraction.jsonl --resolution experiments/kg/er_full_mentions.jsonl
python -m src.kg.stats --scope full
python -m src.kg.coverage --scope full
python -m src.kg.annotation control --input experiments/kg/full_v21_extraction.jsonl
```

All LLM outputs are cached in `experiments/cache/` (not tracked), so a rerun on this machine makes no API calls.

## 1. Before the build

First, three v1 labels were corrected: t0052-t0054 ("... APPLIES_TO outside of the United States") are a place or condition, not a Role, so they are now incorrect (with a note in `annotation_sample.csv`). The gold set goes from 98 to 95 facts. Both prompt versions re-scored with the same rule:

| | Precision | Recall (95 gold) | Pooled recall (118 facts) |
| :--- | :---: | :---: | :---: |
| v1 | 44.3% | 65.3% | 52.5% |
| v2 | 53.7% | 43.2% | 54.2% |
| v2, both runs agree | 72.1% | 32.6% | 35.6% |

Prompt v2.1 (`--prompt-version v2.1`) is v2 plus a rule for contact points (phone, TTY, offices and online accounts as ContactPoints, linked with AVAILABLE_AT to the service or organisation the sentence is about) and two new examples from documents outside the pilot (a VA help line and office, a DMV use tax and fee). Its output goes through four post-filters in `src/kg/postfilter.py`: opening hours typed as TimeLimit, staff typed as Role, UI text ("Request ..." only in Title Case, because "request an appeal" is a real service), and PART_OF relations flipped when one entity is the source of several in a section.

On the 3 annotated documents, without new labels (two runs each; a gold fact counts as found when a triple in the same section has the same relation and mostly the same words in both endpoints):

| | Approx. pooled recall | REQUIRES found (of 46) | AVAILABLE_AT extracted / found (of 17) |
| :--- | :---: | :---: | :---: |
| v1 | 53.4% | 27 | 19 / 11 |
| v2, runs 1-2 | 49.2% / 40.7% | 31 / 22 | 7 / 2, 8 / 4 |
| v2.1, runs 1-2 | 36.4% / 39.0% | 18 / 21 | 16 / 3, 10 / 3 |

v2.1 extracts contact points again, but many are attached to a different source than in the gold triple, so AVAILABLE_AT recall can't be confirmed without labels (5 of the 17 gold facts are social links that the KG drops anyway). On these documents the filters removed 2 staff Roles and 1 opening-hours TimeLimit, and their labelled relations were all incorrect. I decided to go ahead with v2.1 and a single run.

## 2. Extraction

| | |
| :--- | :--- |
| Sections | 4,114 |
| Skipped (short or boilerplate) | 562 |
| Extracted | 3,549 sections (3,194 units, 3,544 planned LLM calls) |
| Lost | 3 sections: 2 blocked by the Azure content filter as false positives ("Escort driver certification"), 1 whose output never completed ("Point & Insurance Reduction Program") |
| Mentions | 28,782 |
| Relations | 20,228, of which 16,947 loadable (3,281, 16.2%, break the type rules) |

Over the corpus the post-filters dropped 58 opening-hours TimeLimits, 49 staff Roles and 36 UI-text entities (with 150 relations attached to them), and flipped 235 PART_OF relations.

The first attempt at the run hung and failed in several ways, which led to these fixes: a 120 s timeout in the LLM client (the SDK default is 10 minutes), retries on timeouts, connection errors and 5xx responses, no caching of empty or unparseable output, content-filter blocks recorded and cached instead of retried, and a cap of 6,000 output tokens per call (the average is about 1,000).

## 3. Entity resolution

| | |
| :--- | :--- |
| Mentions / name groups / entities | 28,782 / 18,017 / 14,732 (14,731 loaded; one is only a social link) |
| Candidate pairs | 31,874 |
| Merged by a rule | 528 (form number 438, acronym 50, alias 40) |
| Rejected because of different values | 3,676 |
| Rejected as generic vs specific | 2,898 |
| Judged by the LLM | 24,772 pairs in 9,230 batched calls; 4,849 confirmed, 19,923 rejected |
| Merges blocked by cannot-link | 1,208 |

9,230 calls is far below the ~21k estimated in `pilot3_report.md`: the real candidate graph is sparser than the random graph used in the simulation, so most groups don't reach five candidates. One judge prompt was blocked by the content filter and treated as "no merge". The largest clusters are forms and documents (DD214 with 15 name groups, bill of sale 13, MV-82 13, non-driver photo ID card 11, MV-44 9) and broad services (disability benefits 9).

## 4. The graph in Neo4j

| Layer | Nodes | Relationships |
| :--- | :--- | :--- |
| Structural | 488 Document, 4,114 Section, 35,659 Span | 4,114 HAS_SECTION, 35,659 HAS_SPAN, 3,626 NEXT |
| Metagraph | 28,782 Mention (1 social) | 28,782 MENTIONS, 16,947 REL |
| Entity layer | 14,731 Entity | 28,781 RESOLVES_TO, 13,277 entity relations |

In the first build, 532 entity relations were not loaded because they break the type rules under the resolved types, 188 because both endpoints resolve to the same entity, and 1 because of a social-media endpoint.

Entities by type and domain (`kg_stats_full.json`; an entity's domain is its most frequent one, 100 entities appear in several domains):

| Type | DMV | SSA | StudentAid | VA | Total |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Requirement | 1,830 | 511 | 1,133 | 1,382 | 4,856 |
| Service | 1,141 | 315 | 810 | 1,266 | 3,532 |
| Document | 966 | 195 | 332 | 383 | 1,876 |
| Outcome | 349 | 160 | 395 | 305 | 1,209 |
| TimeLimit | 327 | 68 | 215 | 220 | 830 |
| ContactPoint | 271 | 64 | 121 | 236 | 692 |
| Amount | 319 | 98 | 139 | 128 | 684 |
| Organization | 197 | 26 | 175 | 173 | 571 |
| Role | 133 | 67 | 104 | 177 | 481 |
| Total | 5,533 | 1,504 | 3,424 | 4,270 | 14,731 |

Entity relations by type: REQUIRES 5,814, LEADS_TO 1,465, AVAILABLE_AT 1,363, HAS_TIME_LIMIT 815, APPLIES_TO 718, PROVIDED_BY 704, EXEMPT_FROM 621, PART_OF 582, ALTERNATIVE_TO 558, HAS_AMOUNT 500, DETERMINED_BY 137. By domain of the source entity: DMV 5,076, VA 3,762, StudentAid 2,967, SSA 1,472. The relations v1 hardly ever produced (ALTERNATIVE_TO, HAS_AMOUNT, EXEMPT_FROM) are now there in the hundreds.

3,355 of the 4,114 sections (81.6%) have at least one mention, which is 94.5% of the sections that are extracted at all. Every mention except the social link resolves to an entity.

The entity degree has median 1, p90 4, max 99 and mean 1.8, and 3,344 entities (22.7%) are isolated. There are 4,130 connected components; the largest has 8,807 entities (59.8%), the next ones 31 and 28, then a long tail (409 pairs, 3,344 singletons). Unlike the pilot graph (largest component 18%), the full graph is mostly connected, through shared agencies, documents and contact points.

Top entities by degree:

| Type | Entities (degree) |
| :--- | :--- |
| Service | VA health care (99); Direct Consolidation Loan (59); federal student loans (58); income-driven repayment plan (56); driver responsibility assessment (55) |
| Organization | DMV (96); loan servicer (59); U.S. Department of Education (49); financial aid office (26); Social Security (24) |
| ContactPoint | DMV office (70); local Social Security office (24); TTY 1-800-325-0778 (22); 1-800-772-1213 (21); local DMV office (17) |
| Document | FAFSA form (65); bill of sale (36); title certificate (25); child's U.S. passport (21); New York State driver license (21) |
| Requirement | acceptable proof of ownership (47); service-connected disability (23); proof of identity (22); Social Security number (15) |
| Role | Veteran (28); dependent student (13); student (13); service member (11); spouse (11) |
| Amount | sales tax (9); fees (8, section-local); no fee (6); $1,000 (5); annual fee (5) |
| TimeLimit | within 10 days (9); immediately (8); six-month grace period (6); 90 days (5); within the past 24 months (5) |
| Outcome | default (8); interest capitalization (8); monthly payments (8); license suspension (7); suspend your driver license (7) |

## 5. dev-500 coverage

All 500 dev-500 examples have their gold section in scope (`kg_coverage_full.json`).

| | All | DMV | SSA | StudentAid | VA |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Gold section has at least one mention | 483 (96.6%) | 122 | 119 | 118 | 124 |
| An entity of the gold section is named in the question | 142 (28.4%) | | | | |
| ... in the reference answer | 315 (63.0%) | | | | |
| ... in the question or the answer | 350 (70.0%) | 95 | 88 | 78 | 89 |

Only 28% of the questions name an entity of their gold section. Most turns are short or depend on the history ("yes", "how do I apply?"), so a graph retriever has to link entities through the conversation and not only from the current question. These numbers didn't change with the hub fix.

## 6. Hub fix

In the first build, vague names such as "application", "other documents", "requirements listed below" and "fee" (an Amount without value) became hubs: Documents and Amounts can merge across domains and value-less names pass the value check, so all these mentions collapsed into one entity that connected unrelated services. Two rules were added to `src/kg/resolve.py` (tests in `tests/test_kg_resolve.py`):

* a name made only of generic words ("application", "other documents", "fee", "benefits", ...) is not resolved and stays an entity of its own section;
* Amounts and TimeLimits without a value are no longer merged across domains.

Entity resolution was re-run from the cache (412 new judge calls, 86 s) and the graph reloaded.

| | Before | After |
| :--- | :---: | :---: |
| Name groups | 17,765 | 18,017 |
| Entities | 14,453 | 14,731 |
| Entity relations | 13,219 | 13,277 |
| Judge calls | 9,411 | 9,230 |
| Isolated entities | 3,238 | 3,344 |
| Connected components | 3,983 | 4,130 |
| Largest component | 8,798 (60.9%) | 8,807 (59.8%) |
| Degree median / p90 / max | 1 / 4 / 100 | 1 / 4 / 99 |

Before the fix the generic hubs had degree 26-31 (application 31, other documents 31, requirements listed below 27, fee 26); after it none of them is in the top lists.

## 7. Cost and runtime

| Stage | LLM calls | Input tokens | Output tokens | Wall time |
| :--- | ---: | ---: | ---: | :--- |
| Extraction (16 workers) | 3,559 (with retries) | 17.47 M | 2.64 M | 34.5 min, plus about 25 min lost to connection drops and content-filter stalls before the fixes |
| Entity resolution, first build (16 workers) | 9,411 | 4.74 M | 1.28 M | 28.7 min (resumed once from the cache after a content-filter crash) |
| Neo4j load | - | - | - | 5 s |
| Total | 12,970 | 22.21 M | 3.93 M | about 63 min of actual run time |

The hub fix added 412 judge calls. No reasoning tokens were used. The price of the deployment isn't recorded in the project, so the cost is not converted to money.

## 8. Control sample

To estimate precision on documents the prompts were not tuned on, `annotation_control.csv` has 30 triples, one from each of 30 random sections (seed 42) that have at least one loadable triple and lie outside all 8 pilot documents. The relation mix is REQUIRES 12, APPLIES_TO 5, PROVIDED_BY 4, HAS_TIME_LIMIT 4, LEADS_TO 3, DETERMINED_BY 1, EXEMPT_FROM 1. The labels were drafted with an LLM (`annotation_control_draft.csv`) and reviewed by me; six of them, all labelled correct, have a note starting with "borderline".

| | Correct / 30 | Precision (Wilson 95% CI) |
| :--- | :---: | :---: |
| Strict (borderline counted as incorrect) | 10 | 33.3% [19.2, 51.2] |
| Lenient (labels as given) | 16 | 53.3% [36.1, 69.8] |

The lenient number is the same as v2 on the annotated pilot (53.7%), so the pilot estimate seems to carry over to unseen documents, but both are below the 65-70% I was aiming for. By relation (lenient): REQUIRES 8/12, APPLIES_TO 2/5, PROVIDED_BY 2/4, HAS_TIME_LIMIT 2/4, LEADS_TO 1/3, DETERMINED_BY 1/1, EXEMPT_FROM 0/1.

The 14 errors, from the notes:

* about 6 endpoints that are not entities at all: headings, form instructions, fragments ("VA cover", "order", "At a DMV office", "restore");
* about 4 wrong types: a law as Organization, a service used as a Role, a target that should be an Amount;
* about 3 wrong relations or directions: reversed beneficiaries (Camp Lejeune), APPLIES_TO where REQUIRES was meant, a waiting time as a deadline;
* 1 relation between two names of the same thing ("TNC PROVIDED_BY rideshare company").

Scores are in `control_scores.json`.
