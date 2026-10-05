# Step 5: KG build on the 8 pilot documents

Neo4j 5 Community (local Docker), scope `pilot`, run id `pilot3_run1`.

This report covers loading the metagraph and the entity layer into Neo4j for the 8 pilot documents only, with the first statistics, coverage numbers and example queries. The full corpus was built later (`full_build_report.md`). The numbers here are after two fixes described in section 8: a tie-break for type conflicts in entity resolution, and keeping social-media contact points out of the entity layer.

To reproduce:

```bash
docker compose up -d neo4j
python -m src.kg.structure
python -m src.kg.load_neo4j                     # scope 'pilot'
python -m src.kg.stats --scope pilot
python -m src.kg.coverage --scope pilot [--examples validation]
python -m pytest tests/test_kg_build.py
```

The extraction and resolution files are not tracked; they come from `python -m src.kg.extract_closed` and `python -m src.kg.resolve run`.

## 1. What was built

The inputs are `pilot3_closed_extraction.jsonl` (the extraction whose triples were annotated in `annotation_sample.csv`) and `er_pilot_batched_mentions.jsonl` (batched LLM judge, lower threshold 0.80). The labelled clusters in `er_pilot_clusters.csv` come from the earlier pairwise run at 0.75; the entity layer can be rebuilt from `er_pilot_mentions.jsonl` if that judge turns out better.

The code: `src/kg/load_neo4j.py` loads one scope and can be re-run (it only deletes and recreates that scope's Mention and Entity nodes, never the structural layer), `src/kg/stats.py` computes the statistics, `src/kg/coverage.py` the QA coverage, and there are tests in `tests/test_kg_build.py` and `tests/test_kg_resolve.py`.

The graph model:

```
(:Section)-[:MENTIONS]->(:Mention {mention_id, name, name_normalized, type, value, kind, alias,
                                  evidence, is_social, run_id, scope, section_id})
(:Mention)-[:REL {type, evidence}]->(:Mention)                  # loadable relations only
(:Mention)-[:RESOLVES_TO]->(:Entity {entity_id, name, type, domain, domains, value, kind,
                                    n_mentions, scope})
(:Entity)-[:<RELATION> {support, section_ids}]->(:Entity)       # the 11 schema relations
```

An entity's `name`, `value` and `kind` are the most frequent non-empty values among its mentions, `type` comes from entity resolution, `domain` is the most frequent domain and `domains` lists all of them. Each entity relation aggregates the mention relations between its two endpoints: `support` counts them and `section_ids` lists their sections. ALTERNATIVE_TO is stored once per pair. Social-media contact points (`is_social`) stay in the metagraph but get no entity.

## 2. Counts

| Layer | Nodes | Relationships |
| :--- | :--- | :--- |
| Structural (8 documents) | 8 Document, 90 Section, 484 Span | 90 HAS_SECTION, 484 HAS_SPAN, 82 NEXT |
| Metagraph | 508 Mention | 508 MENTIONS, 336 REL |
| Entity layer | 377 Entity | 503 RESOLVES_TO, 309 entity relations |

The structural layer of the whole corpus (4 Domain, 488 Document, 4,114 Section, 35,659 Span) is unchanged.

Not loaded: 57 mention relations that break the type rules (14.5% of 393); 5 social-media mentions (all VA); and at entity level 7 relations that are invalid under the resolved types, 5 whose endpoints resolved to the same entity, and 5 with a social-media endpoint. So the 336 loadable mention relations give 319 units of support (336 - 7 - 5 - 5).

| Relation | Mention level | Entity level (edges / support) |
| :--- | :---: | :---: |
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

## 3. Statistics

From `python -m src.kg.stats --scope pilot` (`kg_stats_pilot.json`). Mentions are counted by extracted type, entities by resolved type.

| Type | Mentions | Entities | Mentions per entity |
| :--- | :---: | :---: | :---: |
| Service | 154 | 97 | 1.59 |
| Requirement | 104 | 93 | 1.12 |
| Document | 57 | 43 | 1.33 |
| Organization | 39 | 26 | 1.50 |
| ContactPoint | 37 (5 social) | 23 | 1.39 (non-social) |
| TimeLimit | 35 | 27 | 1.30 |
| Role | 34 | 28 | 1.21 |
| Outcome | 30 | 28 | 1.07 |
| Amount | 18 | 12 | 1.50 |
| Total | 508 | 377 | 1.33 |

61 of the 90 sections have at least one mention, which is 61 of the 63 extracted sections; the other 27 were skipped as short or boilerplate.

The entity degree has median 1, p90 3, max 21 and mean 1.64, with 62 isolated entities (16%). There are 98 connected components, the largest with 69 entities (18.3%). This fragmentation is expected: the 8 documents are about unrelated topics (IRP registration, leased vehicles, SSA appeals, Medicare, financial aid, repayment plans, VA direct deposit, VA housing) and only a few entities like DMV or VA are shared.

Top entities by degree (5 per type, the top 10 are in the JSON):

| Type | Entities (degree) |
| :--- | :--- |
| Service | VA direct deposit information (21); IRP registration (20); Graduated Repayment Plan (18); Veterans Housing Assistance (13); Get Your Aid (12) |
| Document | Schedule A & C pdf (7); FAFSA form (5); NY State Driver License (4); Certificate of Eligibility (COE) (3); check or money order (3) |
| Organization | Department of Veterans Affairs (4); DMV (4); NY State Department of Tax and Finance (3); VA medical center (3); IRB (2) |
| Requirement | authorization from the leasing company to register the vehicle in New York (4); Proof of sales tax payment (4); current or not expired for more than 2 years (3); proof of both identity and age (3); service-connected disability (3) |
| Amount | the amount of interest that accrues between your payments (3); three times greater (3); payment in the amount of $2.50 per vehicle (2); 130.67 percent of your full retirement age benefit (1); 93.33 percent of your full benefit amount (1) |
| Role | outside of the United States (3); Veteran or Servicemember (3); service members (2); surviving spouse of a Veteran (2); administrative law judge (1) |
| TimeLimit | 2 years (3); Monday through Friday (3); 8:00 a.m. to 9:00 p.m. ET (2); between 10 and 30 years (2); every two years (2) |
| ContactPoint | 1 - 518 - 473 - 5834 (2); Call us at 800 - 827 - 1000 (2); DMV office (2); my Social Security account (2); 1 - 800 - 325 - 0778 (1) |
| Outcome | Delayed Retirement Credits (2); benefits reduced (1); build, improve, or keep your current home (1); buy a home (1); comparison of estimated monthly payment amounts (1) |

The hubs are the main service of each document. Some types are clearly questionable ("outside of the United States" as a Role, "three times greater" as an Amount), which the annotation should show.

## 4. Coverage of QA examples

An example is in scope when its gold section belongs to one of the 8 pilot documents. An entity counts as named when one of its surface forms (entity name, names of the resolved mentions, aliases), normalised as in entity resolution, appears as whole words in the question or the reference answer.

| | dev-500 | Validation split |
| :--- | :---: | :---: |
| Examples with a gold section in scope | 3 (all SSA) | 36 (28 SSA, 8 StudentAid) |
| Gold section has a mention | 3 | 35 (97.2%) |
| Entity of the gold section named in the question | 1 | 18 (50.0%) |
| ... in the reference answer | 2 | 23 (63.9%) |
| ... in the question or the answer | 2 | 28 (77.8%) |

dev-500 has only 3 examples in scope, so the script also takes `--examples validation` (outputs `kg_coverage_pilot.json` and `kg_coverage_pilot_validation.json`). None of the validation examples is grounded in the DMV or VA pilot documents. The one gold section without mentions is a short skipped section ("Applying for Medicare Only"). Most of the 8 in-scope examples without a match are conversational turns ("yes", "thank you", "No, neither that.") with an equally short answer, so retrieval over the graph will need the dialogue history, not just string matching.

## 5. Example queries

What does a Service require?

```cypher
MATCH (s:Entity {scope: 'pilot', type: 'Service', name: 'IRP registration'})-[r:REQUIRES]->(x:Entity)
RETURN x.name AS requirement, x.type AS type, r.support AS support, size(r.section_ids) AS sections
ORDER BY support DESC, requirement
```

| requirement | type | support | sections |
| :--- | :--- | :---: | :---: |
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

The real requirements are there (the form, the proofs, the payment, the insurance), but several targets are not requirements at all: they are the kinds of change the form covers ("address change", "add jurisdictions", "transfer plates ..."), "vehicles", and a restriction. This is the main precision problem the annotation has to measure.

Every entity relation can be traced back to its evidence through the metagraph:

```cypher
MATCH (s:Entity {scope: 'pilot', name: 'IRP registration'})-[:REQUIRES]->(x:Entity {name: 'Schedule A & C pdf'})
MATCH (s)<-[:RESOLVES_TO]-(ms:Mention)-[rel:REL {type: 'REQUIRES'}]->(mt:Mention)-[:RESOLVES_TO]->(x)
MATCH (sec:Section)-[:MENTIONS]->(ms)
RETURN sec.section_id AS section, rel.evidence AS evidence
ORDER BY section, evidence
```

| section | evidence |
| :--- | :--- |
| Changes to IRP registration#1_0::10 | IRP-6 submit for all changes listed above |
| Changes to IRP registration#1_0::10 | To make changes to your IRP registration complete Schedule A & C pdf |
| Changes to IRP registration#1_0::59 | Follow the instructions on Schedule A&C [2] IRP-6. |

The form-number rule merged "Schedule A & C pdf", "Schedule A&C [2] IRP-6" and "IRP-6", so the three mention relations give support 3 to one entity relation.

What is an alternative to a given entity? ALTERNATIVE_TO is queried undirected because it's stored once per pair:

```cypher
MATCH (d:Entity {scope: 'pilot'})-[r:ALTERNATIVE_TO]-(alt:Entity)
WHERE toLower(d.name) CONTAINS $name
RETURN d.name AS entity, d.type AS type, alt.name AS alternative, alt.type AS alt_type, r.support AS support
```

For "birth certificate" there are no rows: none of the pilot documents mentions it, so this needs the full graph. For "driver license" there is one row, NY State Driver License (Document) with the alternative "other kinds of proof" (typed Service, which is wrong). ALTERNATIVE_TO is rare in the pilot (2 entity edges).

Which contact points is an organisation available at?

```cypher
MATCH (o:Entity {scope: 'pilot', type: 'Organization'})-[r:AVAILABLE_AT]->(cp:Entity {type: 'ContactPoint'})
RETURN o.name AS organization, cp.name AS contact_point, cp.kind AS kind, cp.value AS value
ORDER BY organization, contact_point
```

| organization | contact_point | kind | value |
| :--- | :--- | :--- | :--- |
| DMV | DMV office | office | - |
| Department of Veterans Affairs | 125 S. Main Street , Suite B | office | 125 S. Main Street , Suite B |
| Department of Veterans Affairs | Muskogee , OK 74401 - 7004 | office | Muskogee , OK 74401 - 7004 |
| IRB | 1 - 518 - 473 - 5834 | phone | 1 - 518 - 473 - 5834 |
| VA Regional Loan Center | contact information for your nearest regional loan center | other | - |

The Organization -> ContactPoint pair works for real contact details (the IRB phone number, the VA address in Muskogee), although the VA address is split into two contact points from two mentions. The five social-media rows (Veterans Benefits Administration -> Facebook, Instagram, LinkedIn, Twitter, YouTube) are gone after the fix in section 8.

## 6. Tests

`tests/test_kg_build.py` (11 tests) checks that the Neo4j counts match the rows built from the input files, that loading twice gives the same counts, that the structural layer is untouched, that every non-social mention has exactly one RESOLVES_TO within its scope, that social contact points get no entity, that deleting a scope leaves the others alone, and that loaded entity relations respect the type rules. These tests need Neo4j and the pilot files and are skipped otherwise. `tests/test_kg_resolve.py` (4 tests) covers the type tie-break, including the NY State Driver License case. Full suite at this point: 92 passed, 4 xfailed.

## 7. Observations

* Precision problems are visible in the graph already: REQUIRES targets that are kinds of change or restrictions, and odd types ("three times greater" as Amount, "outside of the United States" as Role, "other kinds of proof" as Service).
* With 8 unrelated documents the graph is fragmented (16% isolated entities, largest component 18%). Links across documents should grow with the full corpus through shared agencies, documents and contact points.
* When a gold section was extracted it almost always has mentions, and in about 78% of in-scope validation turns an entity of the gold section is named in the question or answer. Conversational turns will need the dialogue history.

## 8. Fixes: type tie-break and social-media links

Type tie-break (`choose_type` in `src/kg/resolve.py`). When mentions with the same name were extracted with different types, the majority type wins; a tie goes to the type under which most of the mentions' relations satisfy the type rules; a remaining tie uses the fixed order Document > Organization > Service > Requirement > Role > Outcome > Amount > TimeLimit > ContactPoint (before, it was the schema order with Service first). Of the 15 names with conflicting types in the pilot, 1 is decided by majority, 8 by relation fit and 6 by the fixed order. Two entities changed type: NY State Driver License (Document 1, Service 1, decided by the order since its 4 relations fit both) from Service to Document, and OSCAR (Service 1, Organization 1, decided by relation fit) from Service to Organization. Entity resolution was re-run with the same judge (111 calls, mostly cached) and the 382 clusters kept the same members.

Social-media contact points (`is_social_contact` in `src/kg/schema.py`): a ContactPoint whose name, value or evidence mentions Facebook, X/Twitter, YouTube, Instagram, LinkedIn, Flickr, TikTok, Pinterest, Snapchat, Threads, Tumblr, Vimeo or Reddit. They stay in the raw output and in the metagraph (`Mention.is_social = true`) but get no entity or entity relation. In the pilot these are the 5 links of the VA "Follow us" footer (Facebook, Instagram, LinkedIn, Twitter, YouTube), each with one AVAILABLE_AT edge from Veterans Benefits Administration; no other domain has any, and there are no false positives. The pilot 3 output was not regenerated because it is the annotated run.

| | Before | After |
| :--- | :---: | :---: |
| Entities | 382 | 377 |
| RESOLVES_TO | 508 | 503 |
| Entity relations | 313 | 309 |
| ContactPoint / Document / Organization / Service entities | 28 / 42 / 25 / 99 | 23 / 43 / 26 / 97 |
| AVAILABLE_AT / PROVIDED_BY edges | 36 / 16 | 31 / 17 |
| Entity relations invalid under the resolved types | 8 | 7 |
| Connected components | 99 | 98 |

The extra PROVIDED_BY edge and the one fewer invalid relation both come from OSCAR becoming an Organization. Coverage and degree statistics did not change.
