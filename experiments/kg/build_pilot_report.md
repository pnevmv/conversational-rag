# Step 5: KG build on the 8 pilot documents

Date: 2026-10-03 · Branch: `kg/build` (from `kg/closed-schema-extraction`, PR #1) · Neo4j 5 Community (local Docker)

This report covers building the metagraph and KG layers in Neo4j for the 8 pilot documents only, and the first statistics and coverage figures. No full-corpus extraction or entity resolution has been run; those wait for the manual annotation scores.

**Revision (2026-10-03):** two fixes, with the pilot KG rebuilt (§9):
1. a tie-break for type conflicts in entity resolution;
2. social-media ContactPoints kept out of the KG layer.

All counts, statistics and queries below are from the rebuilt graph.

## 1. What was built

**Inputs** (scope `pilot`, run id `pilot3_run1`):
- **Extraction:** `pilot3_closed_extraction.jsonl`, the closed-schema extraction whose triples are being annotated (`annotation_sample.csv`).
- **Entity resolution:** `er_pilot_batched_mentions.jsonl`, i.e. the current default (batched LLM confirmation, lower threshold 0.80, with the type tie-break of §9). Your `er_pilot_clusters.csv` comes from the earlier pairwise run (threshold 0.75). If your review favours that judge, the KG layer can be rebuilt from `er_pilot_mentions.jsonl` with a single command.

**Code:**

| Module | Purpose |
|---|---|
| `src/kg/load_neo4j.py` | Metagraph and KG-layer loader for one scope; idempotent (deletes and recreates only the scope's `Mention` and `Entity` nodes, never the structural layer) |
| `src/kg/stats.py` | Per-layer counts, section coverage, entity degree distribution, connected components, top entities per type; works for any scope or `*` |
| `src/kg/coverage.py` | dev-500 (or full-validation) coverage of the gold sections by the graph, for any scope |
| `tests/test_kg_build.py` | 11 loader tests on the pilot data, in a separate `pytest_pilot` scope that is deleted afterwards |
| `tests/test_kg_resolve.py` | 4 tests for type-conflict resolution, including the "NY State Driver License" case |

**Graph model:**
```
(:Section)-[:MENTIONS]->(:Mention {mention_id, name, name_normalized, type, value, kind, alias,
                                  evidence, is_social, run_id, scope, section_id})  # CREATE per extraction
(:Mention)-[:REL {type, evidence}]->(:Mention)                                  # loadable relations only
(:Mention)-[:RESOLVES_TO]->(:Entity {entity_id, name, type, domain, domains, value, kind,
                                    n_mentions, scope})
(:Entity)-[:<RELATION> {support, section_ids}]->(:Entity)                       # 11 schema relation types
```

- **Entity properties:** `name`, `value` and `kind` are the most frequent non-empty values among the entity's mentions. `type` is the type chosen by entity resolution (majority vote, with the tie-break of §9). `domain` is the most frequent domain, and `domains` lists all of them.
- **Entity relations:** each one aggregates the mention-level relations between its two resolved endpoints. `support` counts those relations and `section_ids` lists their sections. ALTERNATIVE_TO is stored once per pair.
- **Social-media ContactPoints** (`is_social: true`) stay in the metagraph but get no RESOLVES_TO, Entity or entity relation.

## 2. Neo4j counts (scope `pilot`)

| Layer | Nodes | Relationships |
|---|---|---|
| Structural (8 documents) | 8 Document, 90 Section, 484 Span | 90 HAS_SECTION, 484 HAS_SPAN, 82 NEXT |
| Metagraph | **508 Mention** | 508 MENTIONS, **336 REL** |
| KG | **377 Entity** | 503 RESOLVES_TO, **309 entity relations** |

The whole database still has 4 Domain, 488 Document, 4,114 Section and 35,659 Span nodes: the structural layer is unchanged.

**Not loaded:**

| Level | Count | Reason |
|---|---:|---|
| Mention relations | 57 | Break the type rules (14.5% of 393 extracted) |
| Mentions | 5 | Social-media ContactPoints (all VA): flagged `is_social`, kept in the metagraph, no RESOLVES_TO |
| Entity relations | 7 | Invalid under the resolved entity types, which can differ from the type a mention was extracted with |
| Entity relations | 5 | Both endpoints resolved to the same entity, so they would be self-loops |
| Entity relations | 5 | One endpoint is a social-media ContactPoint |

The 336 loadable mention relations therefore carry 319 units of entity-level support: 336 − 7 − 5 − 5.

| Relation | Mention level (REL) | Entity level (edges / support) |
|---|---:|---:|
| REQUIRES | 127 | 120 / 125 |
| APPLIES_TO | 49 | 45 / 48 |
| AVAILABLE_AT | 40 | 31 / 31 |
| LEADS_TO | 39 | 36 / 37 |
| HAS_TIME_LIMIT | 31 | 30 / 31 |
| PROVIDED_BY | 17 | 17 / 17 |
| HAS_AMOUNT | 16 | 16 / 16 |
| PART_OF | 8 | 6 / 6 |
| EXEMPT_FROM | 4 | 4 / 4 |
| ALTERNATIVE_TO | 3 | 2 / 2 |
| DETERMINED_BY | 2 | 2 / 2 |

## 3. Statistics (`python -m src.kg.stats --scope pilot`, `kg_stats_pilot.json`)

| Type | Mentions | Entities | Mentions per entity |
|---|---:|---:|---:|
| Service | 154 | 97 | 1.59 |
| Requirement | 104 | 93 | 1.12 |
| Document | 57 | 43 | 1.33 |
| Organization | 39 | 26 | 1.50 |
| ContactPoint | 37 (5 social) | 23 | 1.39 (non-social) |
| TimeLimit | 35 | 27 | 1.30 |
| Role | 34 | 28 | 1.21 |
| Outcome | 30 | 28 | 1.07 |
| Amount | 18 | 12 | 1.50 |
| **Total** | **508** | **377** | **1.33** (503 resolved) |

Mention counts are by extracted type; entity counts are by resolved type.

**Sections with at least one mention:** 61 of 90 (67.8%), or **61 of 63 extractable sections (96.8%)**. The other 27 were skipped as short or boilerplate, and 2 extracted sections produced no entities.

**Entity degree** (entity relations only, both directions):

| Median | p90 | Max | Mean | Isolated entities |
|---:|---:|---:|---:|---:|
| 1 | 3 | 21 | 1.64 | 62 (16%) |

**Connected components of the entity graph:** 98 components, the largest with 69 entities (18.3%). Sizes: one each of 69, 31, 27, 22, 21, 17, 13 and 10; two of 9; and up to 11 small ones of each size below that, down to 62 single entities.

The graph is fragmented. That is expected, since the 8 documents cover unrelated topics (IRP registration, leased vehicles, SSA appeals, Medicare, financial aid, repayment plans, VA direct deposit, VA housing) and only a few entities, such as DMV or VA, are shared across documents.

**Top entities by degree** (5 per type; the full top-10 lists are in the JSON):

| Type | Entities (degree) |
|---|---|
| Service | VA direct deposit information (21); IRP registration (20); Graduated Repayment Plan (18); Veterans Housing Assistance (13); Get Your Aid (12) |
| Document | Schedule A & C pdf (7); FAFSA form (5); NY State Driver License (4); Certificate of Eligibility (COE) (3); check or money order (3) |
| Organization | Department of Veterans Affairs (4); DMV (4); NY State Department of Tax and Finance (3); VA medical center (3); IRB (2) |
| Requirement | authorization from the leasing company to register the vehicle in New York (4); Proof of sales tax payment (4); current or not expired for more than 2 years (3); proof of both identity and age (3); service-connected disability (3) |
| Amount | the amount of interest that accrues between your payments (3); three times greater (3); payment in the amount of $2.50 per vehicle (2); 130.67 percent of your full retirement age benefit (1); 93.33 percent of your full benefit amount (1) |
| Role | outside of the United States (3); Veteran or Servicemember (3); service members (2); surviving spouse of a Veteran (2); administrative law judge (1) |
| TimeLimit | 2 years (3); Monday through Friday (3); 8:00 a.m. to 9:00 p.m. ET (2); between 10 and 30 years (2); every two years (2) |
| ContactPoint | 1 - 518 - 473 - 5834 (2); Call us at 800 - 827 - 1000 (2); DMV office (2); my Social Security account (2); 1 - 800 - 325 - 0778 (1) |
| Outcome | Delayed Retirement Credits (2); benefits reduced (1); build, improve, or keep your current home (1); buy a home (1); comparison of estimated monthly payment amounts (1) |

The hubs are each document's main service, as expected. "Veterans Benefits Administration" (degree 5 before) has left the top list: all its edges were social-media links. Some entity choices are questionable and should show up in the annotation: "outside of the United States" as a Role, "three times greater" as an Amount.

## 4. Coverage of QA examples (`python -m src.kg.coverage`)

An example is in scope when its gold section (from the grounding annotation) belongs to one of the 8 pilot documents. An entity is matched when any of its surface forms (entity name, names of all mentions resolved to it, aliases), normalised as in entity resolution, appears as a whole-word sequence in the question or the reference answer.

| | dev-500 | Full validation split |
|---|---:|---:|
| Examples with a gold section in scope | **3** (all SSA) | **36** (28 SSA, 8 StudentAid) |
| Gold section has ≥ 1 mention | 3 (100%) | 35 (97.2%) |
| Entity of the gold section named in the question | 1 (33%) | 18 (50.0%) |
| … named in the reference answer | 2 (67%) | 23 (63.9%) |
| … named in the question or the answer | 2 (67%) | **28 (77.8%)** |

These figures are unchanged by the revision.

- **The dev-500 sample is too small** (3 examples), so the script also accepts `--examples validation`. Both runs are saved (`kg_coverage_pilot.json`, `kg_coverage_pilot_validation.json`).
- **Two pilot documents have no grounded dialogue turns:** none of the validation examples ground in the DMV or VA pilot documents.
- **The one gold section without mentions** is a short, skipped section ("Applying for Medicare Only", `::1`).
- **Most of the 8 in-scope examples without a match are conversational turns** ("yes", "thank you", "No, neither that.") whose answer is also short or conversational. They will need the dialogue history rather than string matching when the graph is used for retrieval.

## 5. Example queries

**Q1. What does a Service REQUIRE?**

```cypher
MATCH (s:Entity {scope: 'pilot', type: 'Service', name: 'IRP registration'})-[r:REQUIRES]->(x:Entity)
RETURN x.name AS requirement, x.type AS type, r.support AS support, size(r.section_ids) AS sections
ORDER BY support DESC, requirement
```

| requirement | type | support | sections |
|---|---|---:|---:|
| Schedule A & C pdf | Document | 3 | 2 |
| address change | Requirement | 2 | 2 |
| Send photocopies of your proofs of identity. | Requirement | 1 | 1 |
| You can't make changes to your IRP registrations at a DMV local office. | Requirement | 1 | 1 |
| add jurisdictions | Requirement | 1 | 1 |
| additional information is required to process your application | Requirement | 1 | 1 |
| check or money order | Document | 1 | 1 |
| increase or decrease registered weight | Requirement | 1 | 1 |
| name change | Requirement | 1 | 1 |
| proof of NY State insurance | Requirement | 1 | 1 |
| proof of an established place of business | Requirement | 1 | 1 |
| proof of ownership | Requirement | 1 | 1 |
| transfer a vehicle from one fleet to another fleet | Requirement | 1 | 1 |
| transfer plates from one vehicle to another | Requirement | 1 | 1 |
| vehicles | Requirement | 1 | 1 |

**The real requirements are present:** the form, proofs, payment and insurance. **But several targets are not requirements:** they are the kinds of change the form covers ("address change", "name change", "add jurisdictions", "transfer plates …"), "vehicles", and a restriction ("You can't make changes … at a DMV local office"). This is the main precision issue the annotation should quantify.

Every entity relation can be traced back to its evidence through the metagraph:

```cypher
MATCH (s:Entity {scope: 'pilot', name: 'IRP registration'})-[:REQUIRES]->(x:Entity {name: 'Schedule A & C pdf'})
MATCH (s)<-[:RESOLVES_TO]-(ms:Mention)-[rel:REL {type: 'REQUIRES'}]->(mt:Mention)-[:RESOLVES_TO]->(x)
MATCH (sec:Section)-[:MENTIONS]->(ms)
RETURN sec.section_id AS section, rel.evidence AS evidence
ORDER BY section, evidence
```

| section | evidence |
|---|---|
| Changes to IRP registration#1_0::10 | IRP-6 submit for all changes listed above |
| Changes to IRP registration#1_0::10 | To make changes to your IRP registration complete Schedule A & C pdf |
| Changes to IRP registration#1_0::59 | Follow the instructions on Schedule A&C [2] IRP-6. |

Entity resolution merged "Schedule A & C pdf", "Schedule A&C [2] IRP-6" and "IRP-6" through the form-number rule, so the three mention-level relations count as support 3 for one entity relation.

**Q2. What is ALTERNATIVE_TO a given entity?** The relation is queried undirected, because it is stored once per pair.

```cypher
MATCH (d:Entity {scope: 'pilot'})-[r:ALTERNATIVE_TO]-(alt:Entity)
WHERE toLower(d.name) CONTAINS $name
RETURN d.name AS entity, d.type AS type, alt.name AS alternative, alt.type AS alt_type, r.support AS support
```

- **`$name = 'birth certificate'`: no rows.** None of the 8 pilot documents mentions a birth certificate (it appears in SSA and DMV identity-proof pages outside the pilot), so this example can only be answered once the full graph is built.
- **`$name = 'driver license'`:**

| entity | type | alternative | alt_type | support |
|---|---|---|---|---:|
| NY State Driver License | Document | other kinds of proof | Service | 1 |

ALTERNATIVE_TO is rare in the pilot (2 entity edges). "NY State Driver License" is now a **Document**: it was extracted once as Document and once as Service, and the new tie-break (§9) resolves the tie. The alternative, "other kinds of proof", is still typed Service, which the annotation should flag.

**Q3. Which ContactPoints is an Organization AVAILABLE_AT?** This uses the Organization → ContactPoint extra pair.

```cypher
MATCH (o:Entity {scope: 'pilot', type: 'Organization'})-[r:AVAILABLE_AT]->(cp:Entity {type: 'ContactPoint'})
RETURN o.name AS organization, cp.name AS contact_point, cp.kind AS kind, cp.value AS value
ORDER BY organization, contact_point
```

| organization | contact_point | kind | value |
|---|---|---|---|
| DMV | DMV office | office | — |
| Department of Veterans Affairs | 125 S. Main Street , Suite B | office | 125 S. Main Street , Suite B |
| Department of Veterans Affairs | Muskogee , OK 74401 - 7004 | office | Muskogee , OK 74401 - 7004 |
| IRB | 1 - 518 - 473 - 5834 | phone | 1 - 518 - 473 - 5834 |
| VA Regional Loan Center | contact information for your nearest regional loan center | other | — |

- **The extra pair works for real contact details:** the IRB phone number and the VA Muskogee address.
- **The VA street address is split into two ContactPoints** (street and city/ZIP), from two separate mentions.
- **The five social-media rows are gone** (Veterans Benefits Administration → Facebook, Instagram, LinkedIn, Twitter, YouTube; §9). They remain as flagged mentions in the metagraph.

## 6. Tests

`tests/test_kg_build.py` has 11 tests and `tests/test_kg_resolve.py` has 4, all passing. The loader tests need a reachable Neo4j and the local pilot files and are skipped otherwise; the resolve tests need only the pilot file for the driver-licence case.

| Test | Checks |
|---|---|
| Counts | Mention, MENTIONS, REL, Entity, RESOLVES_TO and entity-relation counts in Neo4j equal the rows built from the input files |
| Idempotency | Loading the same scope twice gives identical counts |
| Structural layer | Domain, Document, Section and Span counts are unchanged by a load |
| RESOLVES_TO | Every non-social Mention has exactly one RESOLVES_TO; no RESOLVES_TO crosses scopes; every Entity has at least one mention |
| Social media | Social-media ContactPoints are flagged `is_social`, have no RESOLVES_TO, and no social ContactPoint Entity exists |
| Type ties (resolve) | Majority wins; a tie goes to the type the relations fit; a remaining tie uses the fixed priority; "NY State Driver License" resolves to Document |
| MENTIONS | Every Mention hangs off a Section |
| Scope deletion | Deleting one scope leaves other scopes untouched |
| Rows | Loaded entity relations respect the type rules under the resolved types; ALTERNATIVE_TO is stored once per pair; `support` ≥ number of sections ≥ 1 |

Full suite: **92 passed, 4 xfailed**.

## 7. How to reproduce

```bash
docker compose up -d neo4j
python -m src.kg.structure                      # structural layer (idempotent)
python -m src.kg.load_neo4j                     # scope 'pilot': metagraph + KG layer
python -m src.kg.stats --scope pilot
python -m src.kg.coverage --scope pilot [--examples validation]
python -m pytest tests/test_kg_build.py
```

The extraction and resolution JSONL inputs are not versioned (`.gitignore`). They are regenerated with `python -m src.kg.extract_closed` and `python -m src.kg.resolve run`.

## 8. Observations for the annotation and the full build

1. **Precision issues visible in the graph:**
   - REQUIRES targets that are kinds of change or restrictions (Q1);
   - occasional odd entity types ("three times greater" as Amount, "outside of the United States" as Role, "other kinds of proof" as Service).
   
   The annotation will quantify these.
2. **Type ties:** resolved by the relation-fit and priority tie-break (§9).
3. **Fragmentation.** With 8 unrelated documents, 16% of entities are isolated and the largest component holds 18% of entities. Cross-document links should grow with the full corpus (shared agencies, documents, contact points). The full-corpus stats will show whether they do.
4. **Coverage.** When a gold section was extracted, it almost always has mentions. In about 78% of in-scope validation turns, an entity from the gold section is named in the question or answer. String matching misses conversational turns, which graph retrieval will have to handle through the dialogue history.

## 9. Revision: type tie-break and social-media links

**Type tie-break** (`choose_type` in `src/kg/resolve.py`). When mentions sharing a name were extracted with different types:
1. the majority type wins;
2. a tie goes to the tied type under which most of the mentions' relations satisfy the type rules;
3. a remaining tie uses the fixed priority Document > Organization > Service > Requirement > Role > Outcome > Amount > TimeLimit > ContactPoint (previously the schema's order, Service first).

Of the 15 names with conflicting types in the pilot:

| Decided by | Names |
|---|---:|
| Majority | 1 |
| Relation fit | 8 |
| Fixed priority | 6 |

**Two entities (4 mentions) changed type:**

| Entity | Votes | Rule | Before → after |
|---|---|---|---|
| NY State Driver License | Document 1, Service 1 | priority (all 4 of its relations fit either type) | Service → **Document** |
| OSCAR | Service 1, Organization 1 | relation fit | Service → **Organization** |

The other 13 conflicts resolve to the same type as before. Entity resolution was re-run with the same batched judge (111 calls, mostly cached), and the 382 clusters have identical membership, so only the types changed.

**Social-media ContactPoints** (`is_social_contact` in `src/kg/schema.py`): a ContactPoint whose name, value or evidence mentions Facebook, X/Twitter, YouTube, Instagram, LinkedIn, Flickr, TikTok, Pinterest, Snapchat, Threads, Tumblr, Vimeo or Reddit.

- **Where they go:** they stay in the raw extraction output and in the metagraph (`Mention.is_social = true`), but get no RESOLVES_TO, Entity or entity relation. New extractions also carry the flag in their raw output; the existing pilot 3 output was not regenerated, because it is the annotated run.
- **Dropped per domain:**

  | Domain | Social mentions dropped | Entities dropped | Entity relations dropped |
  |---|---:|---:|---:|
  | DMV | 0 | 0 | 0 |
  | SSA | 0 | 0 | 0 |
  | StudentAid | 0 | 0 | 0 |
  | VA | 5 | 5 | 5 |

  The 5 are the Facebook, Instagram, LinkedIn, Twitter and YouTube links of the VA "Follow us" footer, each with one AVAILABLE_AT edge from Veterans Benefits Administration. There are no false positives in the pilot.

**Effect on the pilot KG:**

| | Before | After |
|---|---:|---:|
| Entities | 382 | **377** |
| RESOLVES_TO | 508 | 503 |
| Entity relations | 313 | **309** |
| ContactPoint entities | 28 | 23 |
| Document entities | 42 | 43 |
| Organization entities | 25 | 26 |
| Service entities | 99 | 97 |
| AVAILABLE_AT edges | 36 | 31 |
| PROVIDED_BY edges | 16 | 17 |
| Entity relations invalid under resolved types | 8 | 7 |
| Connected components | 99 | 98 |

The extra PROVIDED_BY edge and the one fewer invalid relation both come from OSCAR becoming an Organization. Section coverage, degree statistics and QA coverage are unchanged.
