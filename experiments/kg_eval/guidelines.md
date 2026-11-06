# Extraction precision: labelling guidelines

Label every row of `entities_sample150.csv` and `relations.csv` (`relations.csv` has 115 rows, so it is labelled in full; `entities.csv` has 159, so a seeded sample of 150 is labelled). Fill three columns:

* `correct`: `1` or `0`.
* `error_type`: only when `correct` is `0`, one of the types below. If several apply, take the first in the list.
* `note`: optional, a few words.

Read the section in the document when the context or the evidence quote is not enough. Judge only what the row shows, not whether the graph has missed something (recall is not measured here).

## Entities

An entity is **correct** when all four hold:

1. It is a real, useful thing in the text: something a user could ask about or that an answer could name.
2. Its type fits the schema (table below).
3. The name is not truncated, not a whole sentence, and not page or UI text ("click here", "[1]", menu items).
4. All merged aliases (`aliases`, separated by `|`) mean the same thing. Singular/plural, abbreviation and full form, and small spelling variants are fine.

| Error type | Use when |
| :--- | :--- |
| `not_an_entity` | not a thing of the domain: UI text, a fragment, a general word ("information", "you") |
| `wrong_type` | a real entity, but the type does not fit |
| `bad_name` | the right thing, but the name is truncated, a whole clause, or contains junk |
| `wrong_merge` | at least one alias means something different (e.g. "FAFSA form" merged with "FAFSA deadline") |

Types: **Service** (something a citizen applies for, receives or completes: benefit, program, licence, registration, loan, test, procedure), **Organization** (agency, office, school, servicer, dealer), **Document** (form, certificate, proof, card, letter, notice), **Requirement** (condition, obligation, eligibility criterion, restriction), **Amount** (fee, tax, premium, benefit amount, limit), **TimeLimit** (deadline, duration, frequency, waiting period), **Role** (category of person: applicant group, status, relative, official), **Outcome** (result or consequence), **ContactPoint** (phone, website, account, office location, information page).

## Relations

A relation is **correct** when the evidence quote supports it, in the right direction (head → tail), with the right relation type. Judge the relation by the text even if an entity has a small naming issue; a wrong entity is counted in the entity file.

| Error type | Use when |
| :--- | :--- |
| `not_supported` | the quote does not state or clearly imply the relation |
| `wrong_direction` | head and tail are swapped |
| `wrong_relation_type` | the two entities are related, but another relation type fits |
| `negation_lost` | the text says the opposite ("cannot", "not required", "unless") |
| `self_or_circular` | head and tail are the same thing, or the relation restates itself ("filing an appeal REQUIRES appeal must be filed") |

Relation types (head → tail): **REQUIRES** head needs tail; **PROVIDED_BY** head is offered, issued or decided by tail; **HAS_AMOUNT** head costs, pays or is limited by tail; **HAS_TIME_LIMIT** head has the deadline or duration tail; **APPLIES_TO** head is available or relevant to tail; **LEADS_TO** head causes or results in tail; **EXEMPT_FROM** head does not need or fall under tail; **DETERMINED_BY** head's value depends on tail; **AVAILABLE_AT** head can be obtained or looked up at tail; **PART_OF** head is a component or sub-case of tail; **ALTERNATIVE_TO** either can be used instead of the other (symmetric, direction does not matter).

When a relation has several quotes (`||`), it is correct if at least one quote supports it. Rows with "(no quote stored)" are judged from the section.

Score with `python experiments/kg_eval/score_precision.py`.
