# Step 6, Phase 1: Entity Linking on dev-500

Entity linking maps a user turn to entities of the full KG (scope `full`, prompt v2.1: 14,731 entities, 19,067 surface forms). No answers are generated in this phase. The aim is to choose the query and linker for the KG retrievers of Phase 2.

Code: `src/kg_rag/` (`graph_index.py`, `queries.py`, `linker.py`, `eval_linking.py`). Run with `python -m src.kg_rag.eval_linking`. Summary: `phase1_linking.json`; per-example linked entities: `phase1_linking.jsonl` (gitignored).

## 1. Setup

**Examples.** dev-500, the subset used in Step 4. All 500 examples have a gold section from the grounding annotation, including the 31 unanswerable turns, so all 500 are scored. The gold section of 96.6% of examples has at least one entity; this is the ceiling of link recall (96.4% if hub entities are excluded).

**Query variants:**

| Variant | Text |
| :--- | :--- |
| raw | the current user turn |
| rewritten | the Step 4 QueryRewriter output (dialogue history → standalone query); first turns keep the raw turn |
| rewritten + agent | the rewrite followed by the last agent turn |

The rewrites use the same prompt and LLM cache as Step 4: 434 rewrite calls, all cache hits, so no new LLM calls in this phase.

**Linker** (`src/kg_rag/linker.py`):
- **Dense:** bge-small (the Step 4 dense model). The query carries the BGE query prefix; each entity scores the cosine of its best surface form (entity name, names of the mentions resolved to it, aliases).
- **BM25** over one short document per entity (its surface forms, stopwords removed).
- **Fusion:** RRF (k = 60, as in the Step 4 hybrid retriever) over the top-100 of each.
- **Domain filter:** if the predicted domain is confident, only entities seen in that domain are kept.
- **Hub skip:** entities with degree above the 99th percentile (degree > 16; 126 entities, e.g. "VA health care" with 99 relations) are skipped.

**Domain prediction.** Step 4 has no domain classifier, so the prediction is the majority domain of the Step 4 best retrieval (Hybrid + Rewrite + Rerank) top-5 sections. Confidence is the share of the top-5 in that domain, and the prediction counts as confident at ≥ 0.8 (4 of 5), a threshold fixed in advance. Results:
- accuracy 94.8% overall;
- confident on 471 of 500 examples;
- 97.9% accurate when confident.

The Step 4 retrieval was recomputed from the reranker cache and reproduces Step 4 exactly (section R@5 = 67.4%). It is cached for Phase 2 (`step4_dev500.json`, gitignored).

**Metric.** Link recall@k is the share of examples where at least one of the top-k linked entities has a mention in a gold section. 95% Wilson intervals in brackets.

The metric is lenient: an entity mentioned in many sections hits more easily. Two controls are therefore reported:
- **Fan-out:** the number of distinct sections the top-10 entities are mentioned in;
- **Chance:** the recall when each example gets the linked entities of another random example of the same domain (5 permutations).

## 2. Query variants (default linker: RRF, domain filter, hub skip)

| Query | R@1 | R@5 | R@10 | Chance R@10 | Fan-out@10 (median) |
| :--- | :--- | :--- | :--- | ---: | ---: |
| raw | 24.2 [20.7, 28.1] | 41.2 [37.0, 45.6] | 47.4 [43.1, 51.8] | 3.6 | 20 |
| **rewritten** | **29.6** [25.8, 33.7] | **52.2** [47.8, 56.5] | **62.0** [57.7, 66.1] | 5.1 | 22 |
| rewritten + agent | 24.8 [21.2, 28.8] | 49.2 [44.8, 53.6] | 59.4 [55.0, 63.6] | 5.4 | 21 |

- **Rewrite:** it adds about 15 points at R@10 over the raw turn. Only 28% of raw questions name a gold-section entity (Step 5 coverage), and the rewrite restores the referent from the history.
- **Last agent turn:** adding it does not help. It lowers R@1 by 5 points, because the agent turn adds entities of the previous answer.
- **Chance:** chance-level recall is 4–7%, so the hits are not an artefact of fan-out.

## 3. Ablations (rewritten query)

| Linker | R@1 | R@5 | R@10 | Chance R@10 | Fan-out@10 (median / mean) |
| :--- | :--- | :--- | :--- | ---: | ---: |
| default (RRF, domain filter, hub skip) | 29.6 | 52.2 | 62.0 | 5.1 | 22 / 23.5 |
| dense only | 27.2 | 49.2 | 59.2 | 5.3 | 21 / 23.0 |
| BM25 only | 32.8 | 50.0 | 59.4 | 5.0 | 20 / 22.5 |
| no domain filter | 29.6 | 51.6 | 61.8 | 4.8 | 21 / 23.3 |
| gold domain (upper bound for the filter) | 30.6 | 54.2 | 63.8 | 5.2 | 22 / 23.3 |
| **no hub skip** | **33.2** [29.2, 37.4] | **59.6** [55.2, 63.8] | **70.4** [66.3, 74.2] | 7.0 | 29 / 36.5 |
| raw + rewritten fused (RRF), hub skip | 26.0 | 47.6 | 57.8 | 4.7 | 21 / 23.3 |
| raw + rewritten fused (RRF), no hub skip | 30.6 | 53.2 | 65.0 | 6.2 | 25 / 31.8 |

- **Fusion:** RRF beats each generator at R@5 and R@10. BM25 alone has the best R@1 (exact name overlap), dense adds paraphrases.
- **Domain filter:** nearly neutral (+0.2 points at R@10). The predicted domain is right 98% of the time when confident, and wrong-domain entities rarely reach the top-10 anyway. Even the gold domain would add only 2 points.
- **Hub skip:** this is the largest effect, and it is negative. Keeping hubs adds 8.4 points at R@10 (46 more examples hit). The cost is a wider fan-out (median 22 → 29 sections, mean 23.5 → 36.5). Chance recall rises only to 7.0%, so most of these hits are genuine: questions about "VA health care" or "Social Security benefits" are about the hub itself.
- **Fusing raw and rewritten:** this helps doc-switch turns (§4) but costs 4–5 points overall.

## 4. Doc-switch, unanswerable and domain splits

R@10 per split (n in brackets):

| Query / linker | Same document (406) | Doc switch (94) | Unanswerable (31) |
| :--- | :--- | :--- | :--- |
| raw | 43.8 [39.1, 48.7] | **62.8** [52.7, 71.9] | 16.1 [7.1, 32.6] |
| rewritten | 63.5 [58.8, 68.1] | 55.3 [45.3, 65.0] | 67.7 [50.1, 81.4] |
| rewritten + agent | 63.3 [58.5, 67.8] | 42.6 [33.0, 52.6] | 80.6 [63.7, 90.8] |
| rewritten, no hub skip | **72.2** [67.6, 76.3] | 62.8 [52.7, 71.9] | 80.6 [63.7, 90.8] |
| raw + rewritten, no hub skip | 64.8 [60.0, 69.3] | **66.0** [55.9, 74.7] | 58.1 [40.8, 73.6] |

- **Doc-switch turns** are the one place where the raw turn beats the rewrite (62.8% vs 55.3%). A turn that opens a new topic usually names it, and the rewrite tends to pull the previous document's topic back in. The last agent turn makes this worse (42.6%).
- **Fusing raw and rewritten** recovers doc-switch turns (66.0%) but loses on same-document turns. With 94 doc-switch turns, the differences between rows are within the confidence intervals.

R@10 per domain (125 examples each):

| Query / linker | DMV | SSA | StudentAid | VA |
| :--- | :--- | :--- | :--- | :--- |
| raw | 52.0 | 42.4 | 50.4 | 44.8 |
| rewritten | 65.6 | 55.2 | 67.2 | 60.0 |
| rewritten + agent | 60.0 | 56.0 | 62.4 | 59.2 |
| rewritten, no hub skip | 68.8 | 68.8 | 76.0 | 68.0 |

- **SSA:** it gains most from keeping hubs (+13.6). SSA questions name broad entities ("Social Security benefits", "disability benefits"), many of which are hubs.
- **SSA R@1:** it is also the weakest domain at R@1 (17.6% with hub skip), because its entity names are long clauses that overlap with many questions.

## 5. Error analysis (rewritten, no hub skip: 148 misses at R@10)

- **No entity in the gold section** (17 misses, 11%): extraction ceiling.
- **Right topic, different entity node** (most misses). The linker finds entities on the right topic that are distinct nodes from those in the gold section. Examples:
  - "disability benefits" and "enough Social Security credits at this time to qualify" vs gold "monthly disability benefit" and "enough credits";
  - "lose eligibility for federal student aid" vs gold "regaining eligibility".

  Long clause-like entity names and conservative entity resolution split one concept into several nodes. One hop through entity relations, or scoring sections by the similarity of their entities rather than exact identity, should recover part of these.
- **Context-free turns** such as "do not": neither the turn nor its rewrite carries content words.
- **Gold sections listing many items** (e.g. the REAL ID document list): the linker finds "REAL ID", but the gold section's entities are the listed documents.

Entity types of the first hit: Service 210, Requirement 65, Document 28, Outcome 20, other types 29.

## 6. Cost and latency

| | |
| :--- | :--- |
| LLM calls per question | 0.87 (the Step 4 rewrite, only for turns with history; no linking calls) |
| Query encoding (bge-small, batched, CPU) | about 6 ms per query |
| Linking (dense + BM25 + RRF over 14,731 entities) | about 8–9 ms per query (15 ms with the agent turn) |
| One-time | entity export from Neo4j and form embeddings: under 1 minute |

## 7. Decisions for Phase 2

1. **Query:** use the Step 4 rewrite. The last agent turn is not used. The raw turn is fused in only as a doc-switch variant, if Phase 2 shows a QA gain there.
2. **Keep hubs in linking.** Skipping them costs 8 points of R@10, and the p99 cap is too aggressive. The fan-out cost moves to section scoring: in retriever A, an entity's contribution to a section will be down-weighted by the number of sections it is mentioned in (IDF-style). Hubs are also excluded from 1-hop expansion and from the fact subgraph of retriever B, to bound context size.
3. **Keep the domain filter.** It is nearly neutral and cheap, and it bounds the candidate set.
4. **Top-10 linked entities** feed the retrievers. The top-1 is right in only a third of the questions.
5. **Ceiling on the KG paths:** link recall at 70% (R@10) is close to the Step 4 section R@5 of 67.4%, but a linked entity reaches 29 sections at the median. Section ranking in retriever A, not linking, is therefore where KG retrieval will gain or lose against Step 4.

**Limitations.**
- dev-500 only; differences under about 6 points between configurations are within the intervals.
- The hit criterion counts any mention in the gold section, not that the entity is the one the question is about.
- The domain threshold (0.8) and the hub percentile (p99) were fixed before the run, not tuned.
