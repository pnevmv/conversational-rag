# Step 5: KG schema proposal from an open-extraction pilot

Model: `gpt-5.4-nano` (Azure OpenAI), temperature 0, strict JSON schema output.

This is the first part of the KG work: the structural layer in Neo4j, a small open extraction on 32 sections, and the closed schema proposed for the full extraction based on it. Nothing extracted by the LLM was written to Neo4j at this stage.

## 1. Structural layer in Neo4j

Neo4j 5 Community runs in Docker (`docker compose up -d neo4j`, see `docker-compose.yml`). It was chosen over Aura Free because it runs locally, needs no account and has no node limit: Aura Free allows 200k nodes and 400k relationships, and the structural layer alone already has about 40k nodes. The connection settings are `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD` in `.env`, and the client is `src/kg/client.py`.

Section ids are `"<doc_id>::<id_sp>"` (`src.data.loader.make_section_id`), so a RAG result `(doc_id, id_sp)` maps directly to a Section node, and span ids use the same form, so the grounding annotations of the dataset map to Span nodes. There are uniqueness constraints on `Domain.name`, `Document.doc_id`, `Section.section_id` and `Span.sp_id`.

The layer is loaded with `python -m src.kg.structure`. All writes use MERGE, and running it twice gives the same counts: 4 Domain, 488 Document, 4,114 Section and 35,659 Span nodes, with 488 HAS_DOCUMENT, 4,114 HAS_SECTION, 35,659 HAS_SPAN and 3,626 NEXT relationships (4,114 sections minus 488 documents).

## 2. Pilot extraction

`python -m src.kg.extract` writes `experiments/kg/pilot_open_extraction.jsonl` and caches the calls in `experiments/cache/kg_extract/`. The sample is 8 sections per domain (32 in total, `random.Random(42)`), taken only from sections with at least 2 spans and 150 characters. The prompt gives the domain, document title, section heading and text, and asks for open-typed entities `{name, type, evidence}` and relations `{source, relation, target, evidence}`, with a short verbatim quote as evidence.

All 32 calls succeeded in about 30 s. The output has 318 entities and 264 relations, no empty sections, and a median of 8 entities (4-30) and 6 relations (2-25) per section. But there are 139 different entity types and 180 relation types, roughly one new type every two mentions, so open extraction alone doesn't give a usable schema.

The aggregates come from `python -m src.kg.pilot_stats` (`pilot_stats.json`), and the manual type mapping of section 5 is in `pilot_type_mapping.json`.

## 3. Evidence check

Each evidence quote was checked against the section text: verbatim (exact substring after collapsing whitespace), near-verbatim (substring when ignoring case, punctuation and quote characters), or not found.

| | Verbatim | Near-verbatim | Not found | Total |
| :--- | :---: | :---: | :---: | :---: |
| Entities | 265 (83.3%) | 51 (16.0%) | 2 (0.6%) | 318 |
| Relations | 207 (78.4%) | 44 (16.7%) | 13 (4.9%) | 264 |
| All | 472 (81.1%) | 95 (16.3%) | 15 (2.6%) | 582 |

The 15 quotes that were not found were checked by hand, and none of them invents content: 9 join fragments with "..." (each fragment is in the text), 3 stitch list items together without an ellipsis, 1 drops a footnote marker, 1 is a light paraphrase ("apply for" instead of "applying for") and 1 comes from the document title. Most of them are from one DMV fee-table section, e.g. `AdditionalFee -[EXEMPTS]-> FarmRegistrationClass` with the evidence "The classes include ... Farm FAR".

A verbatim quote doesn't mean the triple is right, though. Checking all 20 REQUIRES relations by hand, 13 are correct, 3 point the wrong way (`SupervisedDrivingPractice -[REQUIRES]-> RoadTest`, `VAHealthCareEligibilityCondition -[REQUIRES]-> VAHealthCare`) and 4 have a requirement as the source (`DisabilityReviewRequirement -[REQUIRES]-> CaseReview`). There are also 7 self-loops (`VA Health Care -[HAS_PDF]-> VA Health Care`). All relation endpoints match an extracted entity.

## 4. What types came out

Entity types with at least 3 mentions, and the candidate type they were mapped to:

| Open type | n | Mapped to | Example |
| :--- | :---: | :--- | :--- |
| EligibilityCondition | 29 | Requirement | AgeRequirement: "must be at least 21 years of age" |
| Service | 24 | Service | RoadTest: "before you take your road test" |
| Document | 14 | Document | ValidInspectionSticker |
| Requirement | 11 | Requirement | SupervisedDrivingPractice |
| Outcome | 11 | Outcome | BaseBenefitAmountForLife |
| RegistrationClass | 8 | drop (table rows) | AgriculturalRegistrationClass: "Agricultural AGR" |
| PlateConfiguration | 8 | drop (table rows) | MedallionTaxiPlateConfigurationTnnnnnC |
| Program | 8 | Service | Closed School Discharge |
| Benefit | 6 | Service | DisabilityBenefits |
| Agency | 5 | Agency | Department of Homeland Security (DHS) |
| BenefitStartTiming | 5 | drop (advice) | StartBenefitsBeforeFullRetirementAge |
| Test | 4 | Service | VisionTest |
| Organization | 4 | Agency | Loan Servicer |
| FeeAmount | 4 | Fee | Premium Amount |
| Process | 4 | Service | Application Submission |
| Office, Course, TimePeriod, InformationPage, Fee, Form, DocumentRequirement, DocumentRestriction, Consequence, HealthCoverageOption, LoanProgram, Place, Role | 3 each | various | e.g. TimePeriod: "every 12 months"; InformationPage: "See information about vehicle plates" |

The other 111 types have 1-2 mentions each (Regulation, Website, PhoneNumber, EarningsLimit, Button, LifeExpectancy, RoundingRule, Scholarship, ...).

Relation types with at least 2 mentions include REQUIRES (20), EXEMPTS (8), INCLUDES (7), NOT_INCLUDED_FOR_PLATE_CONFIGURATION (6), APPLIES_TO (5), BASED_ON (4), RESULTS_IN (4), HAS_PDF (4), REJECTS, AVAILABLE_FOR, SET_BY, PROVIDES (3 each) and about 25 more with 2 (IS_PART_OF, TRIGGERED_BY, DEPENDS_ON, REFERENCES, SHOWS, RELATED_TO, ANSWERED_NO, ...). 142 relation types appear only once, many of them REQUIRES with the object built into the name (REQUIRES_VISION_TEST, REQUIRES_AGE_AT_LEAST, REQUIRES_WRITTEN_TEST, ...).

## 5. Mapping onto a candidate schema

Every open type was mapped by hand to a candidate type, a new type, or "drop" (`pilot_type_mapping.json`).

Entities (318 mentions):

| Candidate type | Mentions | Open types merged into it |
| :--- | :---: | :--- |
| Service | 73 | Service, Program, Benefit, Test, Process, Course, LoanProgram, Grant, Scholarship, ... (22 types) |
| Requirement | 63 | EligibilityCondition, Requirement, DocumentRequirement, DocumentRestriction, Restriction, ... (20 types) |
| Document | 26 | Document, Form, Certificate, Ticket, Notice, Application, ... (10 types) |
| Outcome | 22 | Outcome, Consequence, PolicyConsequence, ... (9 types) |
| Fee | 19 | FeeAmount, Fee, Amount, Tax, EarningsLimit, BenefitAmount, Cost, ... (12 types) |
| Agency | 18 | Agency, Organization, Office, Provider, GoverningBody, ... (9 types) |
| Role | 14 | Role, EligibilityGroup, ApplicantType, CitizenshipStatus, ... (9 types) |
| TimeLimit | 8 | TimePeriod, CourseDuration, Deadline, ... |
| Total in candidate types | 243 (76.4%) | |
| Missing type: ContactPoint | 8 (2.5%) | InformationPage, Website, PhoneNumber, Account |
| Drop | 67 (21.1%) | |

Requirement, Service and Document cover half of the mentions and work in every domain. Role and Outcome fit too, but Outcome is the noisiest type: it is often a whole proposition turned into a node (`SpouseSocialSecurityBenefitOnYourRecordMayBeAffected`).

Some types don't fit well. Agency is too narrow: 7 of its 18 mentions are not agencies but schools, loan servicers, dealers and offices, so it should be Organization with a `kind`. Fee is too narrow as well: only 6 of 19 are fees or taxes, the rest are premiums, benefit amounts, earnings limits and costs, so it should be Amount. Both Fee and TimeLimit lose the actual value: only 2 of 19 amount entities have the number in the name (5 in the evidence), and TimeLimits are called `InspectionFrequency` while the evidence says "every 12 months". They need a verbatim `value` property, otherwise they can't answer "how much" or "how long". TimeLimit is rare here (8 mentions) but central to MultiDoc2Dial questions, so it stays.

ContactPoint is missing: phone numbers, websites, accounts and information pages. They are rare in the pilot, but agent turns in MultiDoc2Dial often send the user to a phone number, an office or a website, and without this type those answers have nowhere to attach.

The 67 dropped mentions are table-row categories (19, all 16 RegistrationClass and PlateConfiguration from the same fee-table section), UI or meta content (17: buttons, devices, examples), advice or statistics turned into nodes (13), calculation details (8), places (7, better as a property) and legal references (3, also better as a property).

Relations (264 mentions):

| Candidate relation | Same direction + inverse | Main open types |
| :--- | :---: | :--- |
| REQUIRES | 63 + 0 | REQUIRES, ~30 REQUIRES_* variants, CONDITIONED_ON, APPLIES_WHEN, REJECTS |
| LEADS_TO | 17 + 4 | RESULTS_IN, AFFECTS, TRIGGERS; inverse TRIGGERED_BY, CAUSED_BY |
| EXEMPT_FROM | 4 + 14 | STATES_NOT_REQUIRED; inverse EXEMPTS, NOT_INCLUDED_FOR_... (fee table) |
| APPLIES_TO | 14 + 2 | AVAILABLE_FOR, PAYS_TO, COVERS; inverse QUALIFIES_FOR |
| PROVIDED_BY | 7 + 6 | SET_BY, LICENSED_BY, TAUGHT_BY; inverse PROVIDES, ISSUES, FUNDS |
| HAS_DEADLINE | 9 + 0 | HAS_DURATION, REQUIRED_EVERY, GENERALLY_LAST_UP_TO |
| HAS_FEE | 7 + 0 | CHARGES_FEE, CAPPED_BY, GENERALLY_BETWEEN |
| ALTERNATIVE_TO | 3 + 0 | ALTERNATIVE_TO, ALTERNATIVELY_REQUIRES |
| Total in candidate relations | 150 (56.8%) | 26 of them in the inverse direction |
| Missing: DETERMINED_BY | 18 + 2 | BASED_ON, DEPENDS_ON, VARIES_BY, CALCULATED_USING |
| Missing: AVAILABLE_AT | 16 + 2 | HAS_PDF, USES_PHONE_NUMBER, DONE_AT, CHECK_WITH |
| Missing: PART_OF | 2 + 11 | IS_PART_OF; inverse INCLUDES, IS_COMPOSED_OF |
| Drop | 63 (23.9%) | REFERENCES, SHOWS, RELATED_TO, ANSWERED_NO, ... |

REQUIRES dominates once the REQUIRES_<object> variants are folded in, so the closed prompt has to forbid putting the object in the relation name. The direction is unstable: 41 of 264 relations (15.5%) express a schema relation the other way round (EXEMPTS vs EXEMPT_FROM, INCLUDES vs PART_OF), so the relations need explicit domain -> range definitions. EXEMPT_FROM looks frequent only because of the fee table (14 of 18), but exemption questions ("do I need X if ...") are typical in MultiDoc2Dial, so it stays. HAS_FEE, HAS_DEADLINE and ALTERNATIVE_TO are rare, but ALTERNATIVE_TO covers an important dialogue pattern ("if the school has closed, you may be eligible for a closed school discharge instead"). The dropped quarter is mostly discourse or UI (`ANSWERED_NO`, `DISPLAYS_ICON_FOR`, `IS_FASTEST_AND_MOST_ACCURATE`) and vague RELATED_TO/REFERENCES.

## 6. Other things that matter for the full extraction

* Names are identifiers, not mentions: 218 of 318 names (69%) are CamelCase (`NoSuspensionOrRevocationLast2YearsRequirement`), because the CamelCase instruction for types leaked into names. This hurts entity resolution and linking back to the text, so `name` should be the shortest verbatim noun phrase.
* Many Requirement and Outcome entities are whole clauses. That's fine for Requirement, where the clause is the condition, but such nodes should keep the verbatim clause in `text` and a short `name`.
* There is almost no overlap across sections (only 2 names repeat), because the 32 sections come from 31 documents. Entity resolution can't be judged from this pilot and needs a test on whole documents.
* Tables extract badly: the one fee-table section gave 30 entities and 25 relations (9% of all entities from 3% of the sections), almost all row-level noise.

## 7. Proposed schema

Nine entity types:

| Type | Definition | Properties |
| :--- | :--- | :--- |
| Service | something a citizen can apply for, receive or complete: benefits, programs, licences, registrations, loans, tests, courses | `name`, `kind` |
| Organization (was Agency) | agencies, offices, schools, servicers, dealers, any organisation that provides, issues or decides | `name`, `kind` |
| Document | forms, certificates, proofs, cards, letters, notices | `name`, optional `form_number` |
| Requirement | a condition or obligation: eligibility criteria, documents to present, restrictions | `name`, `text`, `negated` |
| Amount (was Fee) | a monetary value or limit: fee, tax, premium, benefit amount, income limit | `name`, `value`, `kind` |
| TimeLimit | a deadline, duration, frequency or waiting period | `name`, `value` |
| Role | a category of person: applicant groups, statuses, relatives, officials | `name` |
| Outcome | a result or consequence (benefit reduced, licence suspended) | `name`, `text` |
| ContactPoint (new) | a phone number, website, online account, office or information page | `name`, `value`, `kind` |

Ten relations with a fixed direction:

| Relation | Domain -> Range | Pilot mentions |
| :--- | :--- | :---: |
| REQUIRES | Service / Document / Role -> Requirement / Document / Service | 63 |
| LEADS_TO | Service / Requirement / Outcome -> Outcome / Service | 21 |
| DETERMINED_BY (new) | Amount / Service / Outcome -> Requirement / Role / Amount | 20 |
| EXEMPT_FROM | Role / Service / Document -> Requirement / Amount / Service | 18 |
| AVAILABLE_AT (new) | Service / Document -> ContactPoint / Organization | 18 |
| APPLIES_TO | Service / Requirement / Amount / TimeLimit -> Role / Service | 16 |
| PROVIDED_BY | Service / Document / Amount -> Organization | 13 |
| PART_OF (new) | Service / Document / Amount -> Service / Document / Amount | 13 |
| HAS_AMOUNT (was HAS_FEE) | Service / Document -> Amount | 7 |
| HAS_TIME_LIMIT (was HAS_DEADLINE) | Service / Requirement / Document -> TimeLimit | 9 |

ALTERNATIVE_TO (3 mentions) is left out of this list; keeping it would make 11 relations. With the mapping of section 5, this schema covers 251 of the 318 entities (78.9%) and 201 of the 264 relations (76.1%, counting inverse ones once flipped; 75.0% without ALTERNATIVE_TO). Every node and relation keeps a verbatim `evidence` and its `section_id`, and in the metagraph each entity links back to the section where it was mentioned.

For the full run the prompt should have closed type lists with one-line definitions and domain -> range rules, surface noun phrases as names (no CamelCase), a mandatory `value` for Amount, TimeLimit and ContactPoint, the verbatim condition in `text` for Requirements, no object-specific relation names and no self-loops, evidence as one contiguous quote without "...", and a cap on long or table-like sections.

## 8. Open decisions

1. Rename Agency to Organization and Fee to Amount, or keep the names with broader definitions?
2. 10 relations, or 11 with ALTERNATIVE_TO? Keeping it is recommended, for the "instead / or you can" pattern.
3. Add ContactPoint as a 9th type? Recommended, for "where / how do I contact" turns.
4. Cap or skip table-like sections?
5. Run another pilot with the closed prompt on about 2 whole documents per domain before the full run, to measure overlap within documents?

(In the end: both renames, 11 relations, ContactPoint added, a cap of 15 entities per call with `is_table` flags (chunking of long sections came later), and a whole-document pilot, see `pilot2_report.md`.)
