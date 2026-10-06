# Re-annotation sheets

Blank copies of the five sheets used to evaluate the KG extraction and entity resolution. These sheets replace the earlier labels, which had been drafted by an LLM and reviewed.

To keep the labels independent, the old sheets and the LLM drafts (`experiments/triples_draft_labels.csv`, `experiments/er_clusters_draft_labels.csv`, `experiments/kg/*_draft.csv`) were not consulted while labelling.

## Files and order

| # | File | Rows | What to fill |
| :---: | :--- | :---: | :--- |
| 1 | `1_triples_v1.csv` | 140 | `label` for each triple extracted with prompt v1 (3 documents) |
| 2 | `2_missing_v1.csv` | add rows | facts stated in the text that sheet 1 doesn't contain; the texts are in `2_sections.csv` |
| 3 | `3_entity_clusters.csv` | 47 | `label` for each cluster of merged names |
| 4 | `4_triples_v2.csv` | 123 | `label` for each triple extracted with prompt v2, and `gold_id` |
| 5 | `5_control.csv` | 30 | `label` for random triples from the full graph (unseen documents) |

Do sheets 1 and 2 first, because the `gold_id` values in sheet 4 refer to them. Sheets 3 and 5 can be done at any time.

## Labels

`label` is `correct` or `incorrect`. `note` is optional; if a case is debatable, write a note starting with `borderline` (the control precision is reported both with and without these).

A triple is correct when all of this holds:

* the relation is stated in the evidence, in the right direction;
* both endpoints are real entities of the right type (not a heading, an instruction, UI text or a fragment);
* it isn't a relation between two names of the same thing.

Entity types and relations, with their allowed directions, are defined in `src/kg/schema.py`. In short:

| Relation | Meaning | Source -> target |
| :--- | :--- | :--- |
| REQUIRES | the source needs the target | Service / Document / Role / Requirement -> Requirement / Document / Service |
| PROVIDED_BY | offered, issued or decided by | Service / Document / Amount -> Organization |
| HAS_AMOUNT | costs, pays or is limited by | Service / Document -> Amount |
| HAS_TIME_LIMIT | has a deadline, duration or frequency | Service / Requirement / Document -> TimeLimit |
| APPLIES_TO | available to or relevant for | Service / Requirement / Amount / TimeLimit -> Role / Service |
| LEADS_TO | causes or results in | Service / Requirement / Outcome -> Outcome / Service |
| EXEMPT_FROM | does not need, pay or fall under | Role / Service / Document -> Requirement / Amount / Service |
| DETERMINED_BY | value or outcome depends on | Amount / Service / Outcome -> Requirement / Role / Amount |
| AVAILABLE_AT | can be obtained or done at | Service / Document / Organization -> ContactPoint / Organization |
| PART_OF | is a component or sub-case of | Service / Document / Amount -> Service / Document / Amount |
| ALTERNATIVE_TO | can be chosen instead of (either direction) | Service / Document / Requirement, both sides |

## Sheet 2: missing facts

One row per fact that is stated in a section but missing from sheet 1. Use the section texts in `2_sections.csv` (all 31 sections of the 3 documents, also the ones that were skipped, marked `extracted = no`). Use the type and relation names of the schema; rows with a relation the schema doesn't allow are reported and left out. Missing facts get the ids `m01`, `m02`, ... in row order.

## Sheet 3: entity clusters

Each row is one entity that merged several differently written names (`surface_names`). `correct` if all the names refer to the same thing, `incorrect` if at least one doesn't (e.g. "Subsidized loan" and "Unsubsidized loan").

## Sheet 4: gold_id

For a correct v2 triple, `gold_id` says which gold fact it expresses: the `triple_id` of a correct triple in sheet 1 (`t0001`, ...) or a missing fact of sheet 2 (`m01`, ...). Leave it empty if the triple is correct but expresses a fact that isn't in the gold set; it then counts for precision but not for recall.

## Status

Done (October 2026). The labelled files are `1_triples_v1_labeled.csv`, `2_missing_v1.csv`, `3_entity_clusters_labels.csv`, `4_triples_v2.csv` and `5_control_labels.csv`; `2_review.md` and `4_review.md` were the helper pages used while labelling. The labels were copied into the files the scoring scripts read (`annotation_sample.csv`, `annotation_missing.csv`, `er_pilot_clusters.csv`, `annotation_v2.csv`, `annotation_control.csv`), `gold_v1.csv` was rebuilt (110 facts) and all scores were recomputed. The previous labels are in the git history.

After a consistency check, three v1 labels were corrected (t0028-t0030: the licence is the proof of identity, so REQUIRES is reversed), a duplicate missing fact was removed (the old m31, same as m27), and seven correct v2 triples got the gold id of the fact they state.
