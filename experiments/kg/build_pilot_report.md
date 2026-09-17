# Step 5: KG build on the 8 pilot documents

Date: 2026-10-03 · Branch: `kg/build` (from `kg/closed-schema-extraction`, PR #1) · Neo4j 5 Community (local Docker)

This report covers building the metagraph and KG layers in Neo4j for the 8 pilot documents only, and the first statistics and coverage figures. No full-corpus extraction or entity resolution has been run; those wait for the manual annotation scores.

## 1. What was built

**Inputs** (scope `pilot`, run id `pilot3_run1`):
- **Extraction:** `pilot3_closed_extraction.jsonl`, the closed-schema extraction whose triples are being annotated (`annotation_sample.csv`).
- **Entity resolution:** `er_pilot_batched_mentions.jsonl`, i.e. the current default (batched LLM confirmation, lower threshold 0.80). Your `er_pilot_clusters.csv` comes from the earlier pairwise run (threshold 0.75). If your review favours that judge, the KG layer can be rebuilt from `er_pilot_mentions.jsonl` with a single command.

**Code:**

| Module | Purpose |
|---|---|
| `src/kg/load_neo4j.py` | Metagraph and KG-layer loader for one scope; idempotent (deletes and recreates only the scope's `Mention` and `Entity` nodes, never the structural layer) |
| `src/kg/stats.py` | Per-layer counts, section coverage, entity degree distribution, connected components, top entities per type; works for any scope or `*` |
| `src/kg/coverage.py` | dev-500 (or full-validation) coverage of the gold sections by the graph, for any scope |
| `tests/test_kg_build.py` | 10 loader tests on the pilot data, in a separate `pytest_pilot` scope that is deleted afterwards |

**Graph model:**
```
(:Section)-[:MENTIONS]->(:Mention {mention_id, name, name_normalized, type, value, kind, alias,
                                  evidence, run_id, scope, section_id})        # CREATE per extraction
(:Mention)-[:REL {type, evidence}]->(:Mention)                                  # loadable relations only
(:Mention)-[:RESOLVES_TO]->(:Entity {entity_id, name, type, domain, domains, value, kind,
                                    n_mentions, scope})
(:Entity)-[:<RELATION> {support, section_ids}]->(:Entity)                       # 11 schema relation types
```

- **Entity properties:** `name`, `value` and `kind` are the most frequent non-empty values among the entity's mentions. `type` is the majority type from entity resolution. `domain` is the most frequent domain, and `domains` lists all of them.
- **Entity relations:** each one aggregates the mention-level relations between its two resolved endpoints. `support` counts those relations and `section_ids` lists their sections. ALTERNATIVE_TO is stored once per pair.

## 2. Neo4j counts (scope `pilot`)

| Layer | Nodes | Relationships |
|---|---|---|
| Structural (8 documents) | 8 Document, 90 Section, 484 Span | 90 HAS_SECTION, 484 HAS_SPAN, 82 NEXT |
| Metagraph | **508 Mention** | 508 MENTIONS, **336 REL** |
| KG | **382 Entity** | 508 RESOLVES_TO, **313 entity relations** |

The whole database still has 4 Domain, 488 Document, 4,114 Section and 35,659 Span nodes: the structural layer is unchanged.

**Not loaded:**

| Level | Count | Reason |
|---|---:|---|
| Mention relations | 57 | Break the type rules (14.5% of 393 extracted) |
| Entity relations | 8 | Invalid once the endpoints get their majority type, which can differ from the type a mention was extracted with |
| Entity relations | 5 | Both endpoints resolved to the same entity, so they would be self-loops |

The 336 loadable mention relations therefore carry 323 units of entity-level support: 336 − 8 − 5.

| Relation | Mention level (REL) | Entity level (edges / support) |
|---|---:|---:|
| REQUIRES | 127 | 120 / 125 |
| APPLIES_TO | 49 | 45 / 48 |
| AVAILABLE_AT | 40 | 36 / 36 |
| LEADS_TO | 39 | 36 / 37 |
| HAS_TIME_LIMIT | 31 | 30 / 31 |
| PROVIDED_BY | 17 | 16 / 16 |
| HAS_AMOUNT | 16 | 16 / 16 |
| PART_OF | 8 | 6 / 6 |
| EXEMPT_FROM | 4 | 4 / 4 |
| ALTERNATIVE_TO | 3 | 2 / 2 |
| DETERMINED_BY | 2 | 2 / 2 |

## 3. Statistics (`python -m src.kg.stats --scope pilot`, `kg_stats_pilot.json`)

| Type | Mentions | Entities | Mentions per entity |
|---|---:|---:|---:|
| Service | 154 | 99 | 1.56 |
| Requirement | 104 | 93 | 1.12 |
| Document | 57 | 42 | 1.36 |
| Organization | 39 | 25 | 1.56 |
| ContactPoint | 37 | 28 | 1.32 |
| TimeLimit | 35 | 27 | 1.30 |
| Role | 34 | 28 | 1.21 |
| Outcome | 30 | 28 | 1.07 |
| Amount | 18 | 12 | 1.50 |
| **Total** | **508** | **382** | **1.33** |

**Sections with at least one mention:** 61 of 90 (67.8%), or **61 of 63 extractable sections (96.8%)**. The other 27 were skipped as short or boilerplate, and 2 extracted sections produced no entities.

**Entity degree** (entity relations only, both directions):

| Median | p90 | Max | Mean | Isolated entities |
|---:|---:|---:|---:|---:|
| 1 | 3 | 21 | 1.64 | 62 (16%) |

**Connected components of the entity graph:** 99 components, the largest with 69 entities (18.1%). Sizes: one each of 69, 30, 27, 22, 21, 17, 13 and 10; two of 9; and 4–6 small ones of each size below that, down to 62 single entities.

The graph is fragmented. That is expected, since the 8 documents cover unrelated topics (IRP registration, leased vehicles, SSA appeals, Medicare, financial aid, repayment plans, VA direct deposit, VA housing) and only a few entities, such as DMV or VA, are shared across documents.

**Top entities by degree** (5 per type; the full top-10 lists are in the JSON):

| Type | Entities (degree) |
|---|---|
| Service | VA direct deposit information (21); IRP registration (20); Graduated Repayment Plan (18); Veterans Housing Assistance (13); Get Your Aid (12) |
| Document | Schedule A & C pdf (7); FAFSA form (5); Certificate of Eligibility (COE) (3); check or money order (3); Claim for Credit of Sales Tax Paid to Another State (2) |
| Organization | Veterans Benefits Administration (5); Department of Veterans Affairs (4); DMV (4); NY State Department of Tax and Finance (3); VA medical center (3) |
| Requirement | authorization from the leasing company to register the vehicle in New York (4); Proof of sales tax payment (4); current or not expired for more than 2 years (3); proof of both identity and age (3); service-connected disability (3) |
| Amount | the amount of interest that accrues between your payments (3); three times greater (3); payment in the amount of $2.50 per vehicle (2); 130.67 percent of your full retirement age benefit (1); 93.33 percent of your full benefit amount (1) |
| Role | outside of the United States (3); Veteran or Servicemember (3); service members (2); surviving spouse of a Veteran (2); administrative law judge (1) |
| TimeLimit | 2 years (3); Monday through Friday (3); 8:00 a.m. to 9:00 p.m. ET (2); between 10 and 30 years (2); every two years (2) |
| ContactPoint | 1 - 518 - 473 - 5834 (2); Call us at 800 - 827 - 1000 (2); DMV office (2); my Social Security account (2); 1 - 800 - 325 - 0778 (1) |
| Outcome | Delayed Retirement Credits (2); benefits reduced (1); build, improve, or keep your current home (1); buy a home (1); comparison of estimated monthly payment amounts (1) |

The hubs are each document's main service, as expected. Some entity choices are questionable and should show up in the annotation: "outside of the United States" as a Role, "three times greater" as an Amount.

## 4. Coverage of QA examples (`python -m src.kg.coverage`)

An example is in scope when its gold section (from the grounding annotation) belongs to one of the 8 pilot documents. An entity is matched when any of its surface forms (entity name, names of all mentions resolved to it, aliases), normalised as in entity resolution, appears as a whole-word sequence in the question or the reference answer.

| | dev-500 | Full validation split |
|---|---:|---:|
| Examples with a gold section in scope | **3** (all SSA) | **36** (28 SSA, 8 StudentAid) |
| Gold section has ≥ 1 mention | 3 (100%) | 35 (97.2%) |
| Entity of the gold section named in the question | 1 (33%) | 18 (50.0%) |
| … named in the reference answer | 2 (67%) | 23 (63.9%) |
| … named in the question or the answer | 2 (67%) | **28 (77.8%)** |

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
```

| section | evidence |
|---|---|
| Changes to IRP registration#1_0::10 | To make changes to your IRP registration complete Schedule A & C pdf |
| Changes to IRP registration#1_0::10 | IRP-6 submit for all changes listed above |
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
| NY State Driver License | Service | other kinds of proof | Service | 1 |

ALTERNATIVE_TO is rare in the pilot (2 entity edges). This edge also shows a typing problem: "NY State Driver License" was extracted once as Document and once as Service, and the 1:1 tie went to Service by the fixed type order. A proof of identity should be a Document.

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
| Veterans Benefits Administration | Facebook | other | — |
| Veterans Benefits Administration | Instagram | other | — |
| Veterans Benefits Administration | Linkedin | other | — |
| Veterans Benefits Administration | Twitter | other | — |
| Veterans Benefits Administration | YouTube | other | — |

- **The extra pair works for real contact details:** the IRB phone number and the VA Muskogee address.
- **The VA street address is split into two ContactPoints** (street and city/ZIP), from two separate mentions.
- **Half the rows are social-media footer links.** That argues for excluding social-media pages from ContactPoint, or treating that footer as boilerplate (§7 of `pilot3_report.md`: it appears in 6 documents, below the 10-document threshold).

## 6. Tests

`tests/test_kg_build.py` has 10 tests, all passing. They need a reachable Neo4j and the local pilot files, and are skipped otherwise.

| Test | Checks |
|---|---|
| Counts | Mention, MENTIONS, REL, Entity, RESOLVES_TO and entity-relation counts in Neo4j equal the rows built from the input files |
| Idempotency | Loading the same scope twice gives identical counts |
| Structural layer | Domain, Document, Section and Span counts are unchanged by a load |
| RESOLVES_TO | Every Mention has exactly one RESOLVES_TO; no RESOLVES_TO crosses scopes; every Entity has at least one mention |
| MENTIONS | Every Mention hangs off a Section |
| Scope deletion | Deleting one scope leaves other scopes untouched |
| Rows | Loaded entity relations respect the type rules under the resolved types; ALTERNATIVE_TO is stored once per pair; `support` ≥ number of sections ≥ 1 |

Full suite: **87 passed, 4 xfailed**.

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
   - occasional odd entity types ("three times greater" as Amount, "outside of the United States" as Role);
   - social-media ContactPoints.
   
   The annotation will quantify these.
2. **Type ties.** Majority voting with a fixed tie-break order can pick an implausible type (driver licence as Service). A type-aware tie-break, preferring the type allowed by the entity's relations, would be a cheap fix.
3. **Fragmentation.** With 8 unrelated documents, 16% of entities are isolated and the largest component holds 18% of entities. Cross-document links should grow with the full corpus (shared agencies, documents, contact points). The full-corpus stats will show whether they do.
4. **Coverage.** When a gold section was extracted, it almost always has mentions. In about 78% of in-scope validation turns, an entity from the gold section is named in the question or answer. String matching misses conversational turns, which graph retrieval will have to handle through the dialogue history.
