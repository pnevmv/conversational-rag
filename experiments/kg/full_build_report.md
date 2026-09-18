# Step 5: full KG build (prompt v2.1, single run)

Date: 2026-10-03 · Branch: `kg/build` · Model: `gpt-5.4-nano-smirnov` (Azure), reasoning effort none, temperature 0 · Neo4j scope `full`, run id `full_v21`

The whole corpus was extracted with prompt v2.1 in a single run. Entity resolution used the batched judge, the generic-vs-specific rule and a lower threshold of 0.80. Both layers were then loaded into Neo4j. The pilot scope `pilot` is still in the database alongside `full`.

## 1. Before the build

**v1 label correction.** t0052–t0054 ("… APPLIES_TO outside of the United States") were relabelled incorrect: a place or condition, not a Role. They carry a correction note in `annotation_sample.csv`. The gold set drops from 98 to 95 facts, and both versions were re-scored under the same rule:

| | Precision | Recall vs 95 gold | Pooled recall (118 facts) |
|---|---:|---:|---:|
| v1 | 44.3% | 65.3% | 52.5% |
| v2 | 53.7% | 43.2% | 54.2% |
| v2, both runs agree | 72.1% | 32.6% | 35.6% |

**Prompt v2.1** (`--prompt-version v2.1`; v1 and v2 unchanged):
- **Prompt changes:** v2 plus a contact-point rule (phone, TTY, offices and online accounts as ContactPoints, linked with AVAILABLE_AT from the service or organisation the sentence is about).
- **New examples:** two, both from documents outside the pilot: a VA help line and office, and a DMV use tax and fee.
- **Post-filters** (`src/kg/postfilter.py`, 29 unit tests):
  - opening-hours TimeLimits;
  - staff Roles;
  - UI text ("Request …" only in Title Case: "request an appeal" is a real service);
  - PART_OF hubs flipped so the parent is the target.

On the 3 annotated documents, without relabelling (two runs each; "approx." = a gold fact counts as found when a triple in the same section has the same relation and both endpoints mostly the same words):

| | Approx. pooled recall | REQUIRES found (of 46) | AVAILABLE_AT extracted / found (of 17) |
|---|---:|---:|---:|
| v1 | 53.4% | 27 | 19 / 11 |
| v2, runs 1–2 | 49.2% / 40.7% | 31 / 22 | 7 / 2, 8 / 4 |
| v2.1, runs 1–2 | 36.4% / 39.0% | 18 / 21 | 16 / 3, 10 / 3 |

- **What v2.1 restored:** contact points are extracted again.
- **What the matching can't confirm:** many of those contact points are attached to a different source than the gold triple, so AVAILABLE_AT recall can't be confirmed without labels (5 of the 17 gold facts are social links that the KG drops).
- **The filters:** on the 3 documents they removed 2 staff Roles and 1 opening-hours TimeLimit; their relations with a known label were incorrect.
- **Decision:** going ahead with v2.1, single run.

## 2. Extraction

| | |
|---|---:|
| Sections | 4,114 |
| Skipped (short or boilerplate) | 562 |
| Extracted | 3,549 sections (3,194 units, 3,544 LLM calls planned) |
| Lost | **3 sections**: 2 blocked by the Azure content filter as false positives ("Escort driver certification"), 1 whose output never completed (truncated JSON twice, "Point & Insurance Reduction Program") |
| Mentions (entities) | 28,782 |
| Relations | 20,228, of which 16,947 loadable; 3,281 (16.2%) break the type rules and are not loaded |

Post-filter actions over the corpus:

| Action | Count |
|---|---:|
| Opening-hours TimeLimits dropped | 58 |
| Staff Roles dropped | 49 |
| UI-text entities dropped | 36 |
| Relations removed with those entities | 150 |
| PART_OF relations flipped | 235 |

Robustness fixes made during the run:
- **Timeout:** the LLM client now has a 120 s timeout instead of the SDK's 10 minutes.
- **Retries:** timeouts, connection errors and 5xx responses are retried.
- **Invalid output:** an empty or unparseable response is never cached.
- **Content filter:** blocks are recorded and cached, not retried.
- **Output cap:** calls are capped at 6,000 output tokens; the average is about 1,000.

## 3. Entity resolution

| | |
|---|---:|
| Mentions → name groups → **entities** | 28,782 → 17,765 → **14,454** (14,453 loaded; 1 consists only of a social link) |
| Type conflicts resolved | 826 |
| Candidate pairs | 32,502 |
| Merged by rule | 528 (form number 438, acronym 50, alias 40) |
| Rejected: different stated values | 3,653 |
| Rejected: generic vs specific | 2,949 |
| Judged by the LLM | 25,372 pairs in **9,411 batched calls**; 4,876 confirmed, 20,496 rejected |
| Merges blocked by cannot-link | 1,210 |
| Judge prompts blocked by the content filter | 1 (treated as no merge) |

The 9,411 calls are well below the ~21k estimated in `pilot3_report.md`. The real candidate graph is sparser than the simulation's random-graph model, so most groups don't reach five candidates. The largest clusters are form numbers and documents (DD214 15 name groups, bill of sale 13, MV-82 13, non-driver photo ID card 11, MV-44 9) and broad services (disability benefits 9).

## 4. Neo4j (scope `full`)

| Layer | Nodes | Relationships |
|---|---|---|
| Structural | 488 Document, 4,114 Section, 35,659 Span | 4,114 HAS_SECTION, 35,659 HAS_SPAN, 3,626 NEXT |
| Metagraph | **28,782 Mention** (1 social) | 28,782 MENTIONS, **16,947 REL** |
| KG | **14,453 Entity** | 28,781 RESOLVES_TO, **13,219 entity relations** |

Entity relations not loaded:

| Reason | Count |
|---|---:|
| Invalid under the resolved entity types | 532 |
| Both endpoints resolve to the same entity | 188 |
| Social-media endpoint | 1 |

## 5. Graph statistics (`kg_stats_full.json`)

**Entities by type and domain** (domain = an entity's most frequent domain; 112 entities occur in several domains):

| Type | DMV | SSA | StudentAid | VA | Total |
|---|---:|---:|---:|---:|---:|
| Requirement | 1,825 | 502 | 1,127 | 1,348 | 4,802 |
| Service | 1,137 | 300 | 804 | 1,253 | 3,494 |
| Document | 943 | 162 | 326 | 370 | 1,801 |
| Outcome | 349 | 157 | 395 | 305 | 1,206 |
| TimeLimit | 323 | 66 | 213 | 218 | 820 |
| ContactPoint | 271 | 64 | 121 | 236 | 692 |
| Amount | 258 | 81 | 127 | 120 | 586 |
| Organization | 197 | 26 | 175 | 173 | 571 |
| Role | 133 | 67 | 104 | 177 | 481 |
| **Total** | **5,436** | **1,425** | **3,392** | **4,200** | **14,453** |

**Entity relations:**

| By type | Edges | | By domain | Edges |
|---|---:|---|---|---:|
| REQUIRES | 5,782 | | DMV | 5,070 |
| LEADS_TO | 1,459 | | VA | 3,747 |
| AVAILABLE_AT | 1,364 | | StudentAid | 2,962 |
| HAS_TIME_LIMIT | 814 | | SSA | 1,440 |
| APPLIES_TO | 717 | | | |
| PROVIDED_BY | 702 | | | |
| EXEMPT_FROM | 615 | | | |
| PART_OF | 582 | | | |
| ALTERNATIVE_TO | 557 | | | |
| HAS_AMOUNT | 495 | | | |
| DETERMINED_BY | 132 | | | |

The relations v1 never found are now present at corpus scale: ALTERNATIVE_TO 557, HAS_AMOUNT 495, EXEMPT_FROM 615. A relation counts for its source entity's domain.

**Coverage and connectivity:**
- **Sections with at least one mention:** 3,355 of 4,114 (81.6%), or **94.5% of the extractable sections**.
- **Mentions resolved to an entity:** 28,781 of 28,782 (100%; the remaining one is the social link).
- **Entity degree** (entity relations, both directions):

  | Median | p90 | Max | Mean | Isolated entities |
  |---:|---:|---:|---:|---:|
  | 1 | 4 | 100 | 1.83 | **3,238 (22.4%)** |

- **Connected components:** 3,983. The **largest has 8,798 entities (60.9%)**; then one of 31, one of 28, and a long tail of small ones (397 pairs, 3,238 singletons). Unlike the pilot (largest component 18%), the full graph is mostly one connected component, linked through shared agencies, documents and contact points.

**Top entities by degree** (5 per type):

| Type | Entities (degree) |
|---|---|
| Service | VA health care (100); Direct Consolidation Loan (59); federal student loans (58); driver responsibility assessment (55); income-driven repayment plan (55) |
| Organization | DMV (96); loan servicer (59); U.S. Department of Education (49); financial aid office (26); New York State Department of Motor Vehicles (23) |
| ContactPoint | DMV office (70); local Social Security office (24); TTY 1-800-325-0778 (22); 1-800-772-1213 (21); local DMV office (17) |
| Document | FAFSA form (65); bill of sale (36); application (31); other documents (31); title certificate (25) |
| Requirement | acceptable proof of ownership (47); requirements listed below (27); service-connected disability (23); proof of identity (22); Social Security number (15) |
| Role | Veteran (28); dependent student (13); student (13); service member (11); spouse (11) |
| Amount | fee (26); sales tax (9); title certificate fee (7); additional fee (6); annual fee (6) |
| TimeLimit | within 10 days (9); immediately (8); six-month grace period (6); 90 days (5); within the past 24 months (5) |
| Outcome | default (8); interest capitalization (8); monthly payments (8); license suspension (7); suspend your driver license (7) |

**Issue: generic hub entities.** Vague names such as "application", "other documents", "requirements listed below" and "fee" (an Amount with no value) have become hubs. Document and Amount may merge across domains, and value-less generic names pass the value-conflict check, so all such mentions collapse into one entity. They carry little meaning and connect unrelated services. A candidate fix: skip resolution, or drop the entity, for names made only of generic words, or limit cross-domain merges to entities with a value or form number.

## 6. dev-500 coverage (`kg_coverage_full.json`)

All 500 dev-500 examples have a gold section in scope.

| | All | DMV | SSA | StudentAid | VA |
|---|---:|---:|---:|---:|---:|
| Gold section has ≥ 1 entity mention | **483 (96.6%)** | 122 | 119 | 118 | 124 |
| Entity of the gold section named in the question | 142 (28.4%) | | | | |
| … named in the reference answer | 315 (63.0%) | | | | |
| … named in the question or the answer | **350 (70.0%)** | 95 | 88 | 78 | 89 |

Only 28% of questions name an entity of their gold section directly. Most user turns are short or depend on the dialogue history ("yes", "how do I apply?"), so a KG retriever will have to link entities through the conversation, not just the current question.

## 7. Cost and runtime

| Stage | LLM calls | Input tokens | Output tokens | Wall time |
|---|---:|---:|---:|---:|
| Extraction (v2.1, 16 workers) | 3,559 (incl. retries) | 17.47 M | 2.64 M | 34.5 min main run; about 25 min more lost to connection drops and content-filter stalls, before the fixes |
| Entity resolution (batched judge, 16 workers) | 9,411 | 4.74 M | 1.28 M | 28.7 min (21.0 + 7.7 min after a content-filter crash, resumed from the cache) |
| Neo4j load | — | — | — | 5 s |
| **Total** | **12,970** | **22.21 M** | **3.93 M** | about 63 min of productive run time |

No reasoning tokens were used (effort none). Cost = 22.21 M × input price + 3.93 M × output price for the deployment. The Azure price of the `gpt-5.4-nano` deployment isn't recorded in the project, so it isn't converted to currency here.

## 8. Control sample

`annotation_control.csv` holds 30 triples, one from each of 30 random sections (seed 42) that have at least one loadable triple and lie **outside all 8 pilot documents**. This is stricter than outside the 3 annotated ones: the v2 rules were derived from errors seen in the pilot outputs.
- **Format:** the same columns as `annotation_v2_new.csv`. Fill in `label` (correct / incorrect) and optionally `note`. `gold_id`, `suggested_gold_id` and `similar_labelled` don't apply and stay empty.
- **Relation mix:** REQUIRES 12, APPLIES_TO 5, PROVIDED_BY 4, HAS_TIME_LIMIT 4, LEADS_TO 3, DETERMINED_BY 1, EXEMPT_FROM 1.
- **Scoring:** once labelled, the sample gives a precision estimate for the full build on unseen documents (± about 17 points at n = 30).

## 9. Reproduce

```bash
python -m src.kg.extract_closed --all --prompt-version v2.1 --workers 16 --usage-log experiments/kg/full_usage_extract.jsonl --output experiments/kg/full_v21_extraction.jsonl
python -m src.kg.resolve run --input experiments/kg/full_v21_extraction.jsonl --prefix er_full --workers 16 --usage-log experiments/kg/full_usage_er.jsonl
python -m src.kg.load_neo4j --scope full --run-id full_v21 --extraction experiments/kg/full_v21_extraction.jsonl --resolution experiments/kg/er_full_mentions.jsonl
python -m src.kg.stats --scope full
python -m src.kg.coverage --scope full
python -m src.kg.annotation control --input experiments/kg/full_v21_extraction.jsonl
```

All LLM outputs are cached (`experiments/cache/`, not versioned), so a rerun on this machine makes no API calls.
