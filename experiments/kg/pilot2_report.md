# Step 5: closed-schema pilot on whole documents (pilot 2)

Model: `gpt-5.4-nano`, temperature 0, strict JSON schema.

This pilot applies the schema agreed in `schema_proposal.md` to every section of 8 whole documents. It measures extraction quality and how often entities repeat across sections, which is needed to plan entity resolution. Nothing extracted by the LLM was written to Neo4j at this stage.

The schema is in `src/kg/schema.py` (types, definitions, `kind` lists, the domain -> range rules of each relation and the JSON schema), the extractor in `src/kg/extract_closed.py` and the statistics in `src/kg/pilot2_stats.py`.

## 1. What changed from the proposal

* Organization and Amount got their final names. Amount has a `kind` (fee, tax, premium, benefit, limit, other) and a `value`.
* ALTERNATIVE_TO is kept (11 relations in total). It is symmetric, so it is stored in one direction (endpoints ordered by case-folded name) and should be queried undirected.
* ContactPoint is the 9th entity type, with `kind` (phone, website, account, office, other) and `value`.
* Sections are flagged `is_table` in Neo4j (section 2), and there is a cap of 15 entities per call, enforced with `maxItems` in the JSON schema (which the API respects) and checked again in post-processing.
* The pilot uses whole documents: 2 per domain (seed 42) with 5-20 sections each, 8 documents and 90 sections.

## 2. The `is_table` flag

The HTML stored in MultiDoc2Dial has no `<table>` elements (they were removed when the corpus was built); the "fee table" from pilot 1 is actually a list item with a long comma-separated enumeration. So the flag is a text heuristic: a section is `is_table` if one of its spans lists at least 6 comma- or semicolon-separated items of at most 4 words each (state codes, registration classes, counties, deployment locations).

This flags 37 of the 4,114 sections (0.9%): 22 DMV, 10 VA, 5 StudentAid, none in SSA. Two broader rules flagged far too much: numeric density (at least half of the spans with $, % or numbers) caught normal text with phone numbers, years and form numbers, and list density (70% of spans inside `<li>`) caught 220 ordinary requirement lists, which are some of the most useful sections to extract.

The structural layer was reloaded (MERGE, so the counts didn't change): 4 Domain, 488 Document, 4,114 Section, 35,659 Span, with 488 HAS_DOCUMENT, 4,114 HAS_SECTION, 35,659 HAS_SPAN and 3,626 NEXT.

## 3. Sample

| Domain | Document | Sections |
| :--- | :--- | :---: |
| DMV | Register a leased vehicle | 11 |
| DMV | Changes to IRP registration | 16 |
| SSA | Appeal A Decision | 8 |
| SSA | Benefits Planner: Retirement, Applying for Medicare Only | 7 |
| StudentAid | How Financial Aid Works | 16 |
| StudentAid | Graduated Plan | 5 |
| VA | Change Your VA Direct Deposit Information | 15 |
| VA | VA Housing Assistance | 12 |

All 90 calls succeeded in about 63 s with 8 workers, and a rerun came entirely from the cache. None of these sections is `is_table`, so section 8 has an extra run on flagged sections.

## 4. Quality compared with the open pilot

| | Pilot 1 (open, 32 sections) | Pilot 2 (closed, 90 sections) |
| :--- | :---: | :---: |
| Entities / relations kept | 318 / 264 | 511 / 368 |
| Distinct entity / relation types | 139 / 180 | 9 / 11 |
| CamelCase entity names | 218 (69%) | 7 (1.4%) |
| Mean words per name | - | 4.1 |
| Evidence verbatim | 97.4% (exact or near) | 96.8% exact |
| Evidence stitched with "..." | 9 | 0 |
| Self-loops | 7 | 0 |
| Relations with an endpoint that is not an extracted entity | 0 | 2 (dropped) |
| Relations outside the domain -> range rules | n/a (~15.5% inverse) | 44 (12.0%) |

28 evidence quotes don't match the text exactly, but none is invented: in 23 the source has words run together ("areunder", "yourbenefits") and the quote puts the space back, 2 quote the document title, 2 skip a list item in between, and 1 covers an address with words run together. Ignoring whitespace in the check covers the 23 spacing cases.

## 5. Types and properties

| Entity type | n | % |
| :--- | :---: | :---: |
| Service | 160 | 31.3 |
| Requirement | 101 | 19.8 |
| Document | 60 | 11.7 |
| Organization | 40 | 7.8 |
| TimeLimit | 37 | 7.2 |
| Outcome | 35 | 6.8 |
| ContactPoint | 34 | 6.7 |
| Role | 26 | 5.1 |
| Amount | 18 | 3.5 |

Relations: REQUIRES 129, LEADS_TO 51, AVAILABLE_AT 45, APPLIES_TO 45, HAS_TIME_LIMIT 32, PROVIDED_BY 22, PART_OF 20, HAS_AMOUNT 13, EXEMPT_FROM 6, DETERMINED_BY 3, ALTERNATIVE_TO 2. Every type and relation is used, though DETERMINED_BY and ALTERNATIVE_TO are rare. ContactPoint is much more frequent than in pilot 1 (34 vs 8), so adding it was worth it.

`value` is filled for all 37 TimeLimits and 32 of 34 ContactPoints. 6 of the 18 Amounts have no value, but they are generic mentions without a figure ("fees", "lower payments"), so leaving it empty is right and `value` stays optional. `text` is filled for all Requirements and Outcomes, and 5 entities are `negated`.

`kind` distribution: Organization agency 17, office 14, servicer 2, other 7; Amount benefit 5, fee 4, premium 3, limit 2, other 4; ContactPoint phone 11, office 8, website 5, account 3, other 7; Service other 65 (41%), program 31, benefit 23, procedure 19, loan 14, registration 8. The "other" Services are mostly appeals and hearings ("Reconsideration", "Appeals Council review"), insurance ("Medicare Part B") and online tools ("Loan Simulator"), so adding `appeal`, `insurance` and `online_tool` would cover most of them.

44 relations (12.0%) break the type rules; they are kept and flagged. The most common patterns are Organization AVAILABLE_AT ContactPoint (an office's phone or address, 9) and Requirement REQUIRES Document ("proof of address requires a utility bill", 4), which both make sense and could be allowed. The rest (Service AVAILABLE_AT Service 3, and 22 other pairs with 1-2 each) can be dropped at load time. With those two pairs allowed the violation rate drops to 31/368 (8.4%).

## 6. Entity overlap

Overlap within each document, comparing entities by (name, type):

| | Exact name (case-insensitive) | Lightly normalised (no articles, punctuation, plural s, parentheses) |
| :--- | :---: | :---: |
| Mentions | 511 | 511 |
| Distinct entities per document | 460 | 458 |
| Entities in 2+ sections of their document | 36 (87 mentions) | 35 (87 mentions) |
| Entities shared by 2+ of the 8 documents | 6 | 9 |

Exact repetition is low: only 7.8% of the distinct entities come back within a document, mostly the main subject of the document ("IRP registration" in 6 of 16 sections). Light normalisation merges only 2 more. The remaining duplicates are aliases and variants: "Schedule A & C pdf", "Schedule A / C IRP6", "Schedule A&C [2] IRP-6" and "IRP-6" are the same form; "DMV", "NYS DMV" and "DMV local office" overlap; "VA home loan benefits", "VA-backed home loan" and "VA direct home loan" are related; an address appears in two truncated forms. The same name also gets different types within a document 12 times (va.gov as ContactPoint and Organization, FAFSA form as Document and Service, reconsideration as Service and Outcome). Links across documents exist (DMV, VA, loan servicer, proof of identity, NY State insurance ID card), but the sample is too small to say how far they go.

So entity resolution should look for candidates first within a document and then within a domain, using name embeddings with the evidence context (bge-small), acronyms (DMV and Department of Motor Vehicles) and form numbers (IRP-6, MV-232), with an LLM to confirm. Compatible types (Document/Service, Organization/ContactPoint) should be allowed as candidates and the type chosen during resolution. Every raw mention stays a node linked to its section, and the resolved entities form the KG layer, as in chapters 5-6 of the book.

## 7. Entity cap

8 of the 90 sections hit the cap of 15 entities, i.e. 8 of the 67 sections with any entities (12%). None of them is `is_table`: they are simply the longest sections (890-2,932 characters, against a median of 351 for the rest). In the corpus 698 sections are longer than 890 characters and 268 longer than 1,500, so with a flat cap about one section in six would lose entities. The proposal is to keep the cap of 15 per call but split sections longer than about 1,500 characters into chunks of about 1,000 characters along span boundaries, each with its own cap.

## 8. Extra run on `is_table` sections

Two flagged sections per domain where possible (SSA has none, so 6 sections; `pilot2_table_extraction.jsonl`, `pilot2_table_stats.json`):

| Section | Characters | Entities | Relations |
| :--- | :---: | :---: | :---: |
| DMV: Restore license after revocation | 4,178 | 15 (cap) | 9 |
| DMV: Exchange your out-of-state driver license | 1,222 | 15 (cap) | 8 |
| StudentAid: Choosing a School | 410 | 5 | 3 |
| StudentAid: Contracting Information | 458 | 6 | 5 |
| VA: File a Supplemental Claim | 287 | 6 | 4 |
| VA: Agent Orange Registry Exam | 1,316 | 7 | 6 |

The closed prompt no longer turns every item of an enumeration into an entity (pilot 1 listed all 8 registration classes); it keeps the useful ones, like forms, offices and eligible locations. The two cap hits come from the length of the sections, not from the enumerations. 76 of 85 quotes are exact and 2 near-verbatim. Of the 7 misses, 5 join the lead-in sentence of a list ("You must have served in one of these ways:") with a later item without "...", 1 quotes the title and 1 has a mangled word. Enumerations still invite stitched quotes, but the verbatim check catches them.

## 9. Planning the full run

562 sections are shorter than 40 characters ("Related PDFs:", "show mydmv button in megamenu:"); all 23 empty sections of the pilot are among them, and every pilot section of 40 characters or more produced entities. 1,059 sections share their exact text with another one (349 distinct texts, e.g. the VA "Call us" footers). Skipping the short sections and extracting each distinct text once gives 3,194 LLM calls instead of 4,114, before chunking. Footer contact points (social links, VA hotlines) would then become a few shared nodes instead of hundreds of copies.

## 10. Open decisions

1. Allow Organization as an AVAILABLE_AT source and Requirement as a REQUIRES source (recommended).
2. Drop relations that break the type rules at load time but keep them in the raw output (yes).
3. Add the Service kinds `appeal`, `insurance` and `online_tool` (yes).
4. Skip sections under 40 characters and extract identical texts once (yes).
5. Keep the cap per call and chunk sections over ~1,500 characters, or keep a flat cap per section.
6. The entity resolution approach above, which has to be fixed before the full run because it determines what the extraction output must contain.

(All of these were adopted; see `pilot3_report.md`.)
