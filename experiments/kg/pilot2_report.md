# Step 5: closed-schema pilot on whole documents

Date: 2026-10-03 · Branch: `kg/closed-schema-extraction` · Model: `gpt-5.4-nano-smirnov`, temperature 0, strict JSON schema

This pilot applies the reviewed schema (decisions 1–5 on `schema_proposal.md`) to every section of 8 whole documents. It measures extraction quality and the cross-section entity overlap needed to plan entity resolution. Nothing extracted by the LLM has been written to Neo4j.

## 1. Decisions implemented

| Decision | Implementation |
|---|---|
| 1. Organization and Amount | Renamed. Amount has `kind` ∈ {fee, tax, premium, benefit, limit, other} and `value` |
| 2. ALTERNATIVE_TO kept, symmetric | 11 relations. ALTERNATIVE_TO is stored in one canonical direction (endpoints ordered by case-folded name) and is meant to be queried undirected |
| 3. ContactPoint | 9th entity type, with `kind` ∈ {phone, website, account, office, other} and `value` |
| 4. Tables flagged, cap of 15 | `Section.is_table` in Neo4j (37 sections, see §2). The cap of 15 entities is enforced through `maxItems` in the strict JSON schema, which the API honours, and checked again in post-processing. It applies to every section |
| 5. Whole-document pilot | 2 documents per domain (seed 42) with 5–20 sections each: 8 documents, 90 sections |

The schema lives in `src/kg/schema.py` (types, definitions, `kind` lists, domain → range rules for each relation, and the JSON schema). The extractor is `src/kg/extract_closed.py` and the aggregation is `src/kg/pilot2_stats.py`.

## 2. `is_table` flag

**MultiDoc2Dial's stored HTML has no `<table>` elements;** they were removed when the corpus was built. The "fee table" section from pilot 1 is really a list item holding a long comma-separated enumeration. The flag is therefore a text heuristic: a section is `is_table` if one of its content spans enumerates **at least 6 comma- or semicolon-separated items of at most 4 words each**, such as state codes, registration classes, counties or deployment locations.

| Domain | Flagged sections |
|---|---:|
| DMV | 22 |
| VA | 10 |
| StudentAid | 5 |
| SSA | 0 |
| **Total** | **37 of 4,114 (0.9%)** |

Two broader rules were tried and rejected:
- **Numeric density** (≥ 50% of spans containing $, % or numbers): it flagged ordinary prose with phone numbers, addresses, years and form numbers.
- **List density** (≥ 70% of spans inside `<li>`): it flagged 220 ordinary requirement lists, which are among the most useful sections to extract.

Neo4j after the reload (counts unchanged, MERGE is idempotent): 4 Domain, 488 Document, 4,114 Section (37 with `is_table = true`), 35,659 Span; 488 HAS_DOCUMENT, 4,114 HAS_SECTION, 35,659 HAS_SPAN, 3,626 NEXT.

## 3. Pilot sample

| Domain | Document | Sections |
|---|---|---:|
| DMV | Register a leased vehicle | 11 |
| DMV | Changes to IRP registration | 16 |
| SSA | Appeal A Decision | 8 |
| SSA | Benefits Planner: Retirement, Applying for Medicare Only | 7 |
| StudentAid | How Financial Aid Works | 16 |
| StudentAid | Graduated Plan | 5 |
| VA | Change Your VA Direct Deposit Information | 15 |
| VA | VA Housing Assistance | 12 |

90/90 calls succeeded in about 63 s with 8 workers. A rerun was served fully from the cache. None of the 90 sections is `is_table`, so a supplementary run on flagged sections is reported in §8.

## 4. Quality compared with the open pilot

| Metric | Pilot 1 (open, 32 sections) | Pilot 2 (closed, 90 sections) |
|---|---:|---:|
| Entities / relations kept | 318 / 264 | 511 / 368 |
| Distinct entity / relation types | 139 / 180 | 9 / 11 (closed) |
| CamelCase entity names | 218 (69%) | 7 (1.4%) |
| Mean words per name | — | 4.1 |
| Evidence verbatim (exact or near) | 97.4% | 96.8% exact |
| Evidence stitched with "…" | 9 | 0 |
| Self-loops | 7 | 0 |
| Relations with an endpoint that isn't an extracted entity | 0 | 2 (dropped) |
| Relations outside the domain → range rules | n/a (~15.5% inverse) | 44 (12.0%) |

**Evidence misses: 28 quotes, none invented.**

| Cause | n |
|---|---:|
| The source text has words run together ("areunder", "yourbenefits") and the quote restores the spacing | 23 |
| Quote taken from the document title | 2 |
| Quote skips an intermediate list item | 2 |
| Quote spans an address with words run together | 1 |

Ignoring whitespace in the check would cover the 23 spacing cases.

## 5. Types and properties

| Entity type | n | % | | Relation | n |
|---|---:|---:|---|---|---:|
| Service | 160 | 31.3 | | REQUIRES | 129 |
| Requirement | 101 | 19.8 | | LEADS_TO | 51 |
| Document | 60 | 11.7 | | AVAILABLE_AT | 45 |
| Organization | 40 | 7.8 | | APPLIES_TO | 45 |
| TimeLimit | 37 | 7.2 | | HAS_TIME_LIMIT | 32 |
| Outcome | 35 | 6.8 | | PROVIDED_BY | 22 |
| ContactPoint | 34 | 6.7 | | PART_OF | 20 |
| Role | 26 | 5.1 | | HAS_AMOUNT | 13 |
| Amount | 18 | 3.5 | | EXEMPT_FROM | 6 |
| | | | | DETERMINED_BY | 3 |
| | | | | ALTERNATIVE_TO | 2 |

Every type and relation is used. DETERMINED_BY and ALTERNATIVE_TO are rare in this sample. ContactPoint (34) is far more frequent than in pilot 1 (8), which confirms decision 3.

**`value` fill:**
- **TimeLimit:** 37/37.
- **ContactPoint:** 32/34.
- **Amount:** 12/18. The 6 without a value are generic mentions where the text states no figure ("fees", "lower payments", "a higher payment"). Leaving them empty is correct, so `value` should stay optional.

**`text` fill:** Requirement 101/101 and Outcome 35/35. **`negated`:** 5 entities.

**`kind` distribution:**
- **Organization:** agency 17, office 14, servicer 2, other 7.
- **Amount:** benefit 5, fee 4, premium 3, limit 2, other 4.
- **ContactPoint:** phone 11, office 8, website 5, account 3, other 7.
- **Service:** other 65 (41%), program 31, benefit 23, procedure 19, loan 14, registration 8. The "other" Services are mostly appeals and hearings ("Reconsideration", "Appeals Council review"), insurance ("Medicare Part B"), and online tools ("Loan Simulator", "direct deposit feature"). Adding `appeal`, `insurance` and `online_tool` would cover most of them.

**Schema violations (44 relations, 12.0%; kept and flagged).** The main patterns:

| Pattern | n | Suggested handling |
|---|---:|---|
| Organization AVAILABLE_AT ContactPoint (an office's phone number or address) | 9 | **Widen:** add Organization to AVAILABLE_AT sources |
| Requirement REQUIRES Document ("proof of address requires a utility bill") | 4 | **Widen:** add Requirement to REQUIRES sources |
| Service AVAILABLE_AT Service | 3 | Drop at load time |
| 22 other type pairs (1–2 each) | 28 | Drop at load time |

With the two widenings, the violation rate falls to 31/368 (8.4%).

## 6. Entity overlap and implications for entity resolution

Overlap was measured within each document, comparing entities by (name, type).

| | Exact name (case-insensitive) | Lightly normalised (no articles, punctuation, plural *s* or parentheticals) |
|---|---:|---:|
| Mentions | 511 | 511 |
| Distinct entities per document | 460 | 458 |
| Entities mentioned in ≥ 2 sections of their document | 36 (87 mentions) | 35 (87 mentions) |
| Entities shared by ≥ 2 of the 8 documents | 6 | 9 |

**Findings:**
1. **Exact repetition is low.** Only 7.8% of distinct entities recur within a document, mostly the document's main subject ("IRP registration" in 6 of 16 sections, "graduated repayment plan" in 4 of 5).
2. **Lexical normalisation adds almost nothing,** merging only 2 entities. The duplicates that remain are **aliases and variants**:
   - "Schedule A & C pdf", "Schedule A / C IRP6", "Schedule A&C [2] IRP-6" and "IRP-6" are one form.
   - "DMV", "NYS DMV" and "DMV local office" overlap.
   - "VA home loan benefits", "VA - backed home loan" and "VA direct home loan" are related.
   - The address "Room 136Swan Street Building…" appears in two truncated forms.
3. **The same entity sometimes gets different types:** 12 names within a document, e.g. *va.gov* (ContactPoint / Organization), *FAFSA form* (Document / Service), *certified check* (Document / Requirement), *reconsideration* (Service / Outcome).
4. **Cross-document links do exist** (DMV, VA, loan servicer, proof of identity, NY State insurance ID card), but this sample is too small to measure how far they reach.

**Proposed entity resolution:**
- **Candidates:** within a document first, then within a domain. Use embedding similarity of the name plus evidence context (bge-small, already in the project), acronym expansion (DMV ↔ Department of Motor Vehicles, IRB), and fuzzy matching of form numbers (IRP-6, MV-232).
- **Confirmation:** an LLM decides on each candidate group.
- **Types:** compatible type pairs (Document/Service, Organization/ContactPoint) are allowed as merge candidates, and a type is chosen during resolution.
- **Metagraph:** every raw mention stays a node linked to its Section. Resolved entities form the KG layer, matching the book's ch. 5–6 design.

## 7. Entity cap

- **Main pilot:** 8 of 90 sections hit the 15-entity cap, which is 8 of the 67 sections with any entities (12%). **None of them is `is_table`.** They are the longest sections in the sample, at 890–2,932 characters against a median of 351 for the rest.
- **Corpus scale:** 698 sections exceed 890 characters and 268 exceed 1,500. Under a flat cap, about 1 section in 6 would lose entities.
- **Table sections:** see §8.

Recommendation (decision 7 below): keep the cap of 15 per LLM call, but **split sections longer than about 1,500 characters into span-aligned chunks** of about 1,000 characters, each with its own cap. This keeps table sections bounded while long prose sections lose nothing.

## 8. Supplementary run: `is_table` sections

There are 2 flagged sections per domain where available. SSA has none, so the run covers 6 sections. Output is in `pilot2_table_extraction.jsonl` and `pilot2_table_stats.json`.

| Section | Characters | Entities (raw) | Relations |
|---|---:|---:|---:|
| DMV: Restore license after revocation | 4,178 | 15 (cap) | 9 |
| DMV: Exchange your out-of-state driver license | 1,222 | 15 (cap) | 8 |
| StudentAid: Choosing a School | 410 | 5 | 3 |
| StudentAid: Contracting Information | 458 | 6 | 5 |
| VA: File a Supplemental Claim | 287 | 6 | 4 |
| VA: Agent Orange Registry Exam | 1,316 | 7 | 6 |

The closed prompt no longer lists every enumerated item as an entity, as pilot 1 did with the 8 registration classes. It keeps the useful ones: forms, offices, eligible service locations. The two cap hits come from **section length**, not from the enumeration itself.

Evidence: 76 of 85 quotes are exact and 2 near-verbatim. The 7 misses:
- **5** join a list's lead-in sentence ("You must have served in one of these ways:") to a list item further down, without "…".
- **1** quotes the document title.
- **1** contains a mangled word ("re - livcensure").

Enumerations thus invite stitched quotes even under the closed prompt. The verbatim check catches them, so they can be dropped or repaired at load time.

## 9. Full-run plan

- **Boilerplate:**
  - 562 sections are shorter than 40 characters ("Related PDFs:", "show mydmv button in megamenu:"). All 23 empty sections in the pilot fall in this group, and every pilot section of 40+ characters produced entities.
  - 1,059 sections share their exact text with another section (349 distinct texts, e.g. VA "Call us" footers).
  - **Proposal:** skip sections under 40 characters, and extract each distinct text once, linking the result to every section that contains it. That makes **3,194 LLM calls instead of 4,114** (before any chunking of long sections).
- **Footer entities:** social-media links (Facebook, Instagram, …) and VA hotline numbers show up as ContactPoints in many VA documents. Deduplicating by text keeps them as a few shared hubs rather than hundreds of copies.

## 10. Decisions for review

1. **Widen the domain → range rules:** add Organization as an AVAILABLE_AT source and Requirement as a REQUIRES source? Recommended: yes.
2. **Drop schema-violating relations** at load time (8.4% after the widening)? Recommended: drop, but keep them in the raw JSONL.
3. **Extend Service kinds** with `appeal`, `insurance` and `online_tool`? Recommended: yes.
4. **Skip sections under 40 characters and deduplicate identical texts** in the full run? Recommended: yes.
5. **Cap scope:** keep 15 per LLM call but chunk sections over ~1,500 characters (recommended), or apply the flat cap of 15 per section as now?
6. **Entity resolution approach** (embedding + acronym + form-number candidates, LLM confirmation, metagraph of mentions): approve before the full run, since it sets what the extraction output must contain.
