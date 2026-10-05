# Step 6, phase 1: entity linking on dev-500

Entity linking maps a user turn to entities of the full graph (scope `full`, prompt v2.1: 14,731 entities, 19,067 surface forms). No answers are generated in this phase; the goal is to choose the query and the linker settings for the retrievers of phase 2.

Code is in `src/kg_rag/` (`graph_index.py`, `queries.py`, `linker.py`, `eval_linking.py`):

```bash
python -m src.kg_rag.graph_index --scope full
python -m src.kg_rag.eval_linking
```

The summary is written to `phase1_linking.json` and the linked entities per question to `phase1_linking.jsonl` (not tracked).

## 1. Setup

All 500 dev-500 examples have a gold section in the grounding annotation, including the 31 unanswerable turns, so all of them are scored. In 96.6% of them the gold section has at least one entity, which is the ceiling for link recall (96.4% without hub entities).

Three query variants are compared:

* raw: the current user turn;
* rewritten: the Step 4 rewrite (dialogue history to standalone query); first turns keep the raw turn;
* rewritten + agent: the rewrite followed by the last agent turn.

The rewrites use the same prompt and cache as Step 4 (434 calls, all from the cache), so this phase makes no new LLM calls.

The linker (`linker.py`) has two candidate generators. The dense one uses bge-small, the Step 4 dense model: the query gets the BGE query prefix, and each entity scores the cosine of its best surface form (its name, the names of the mentions resolved to it, aliases). The sparse one is BM25 over a short document per entity made of its surface forms without stopwords. The top 100 of each are fused with RRF (k = 60, as in the Step 4 hybrid retriever). There are two optional filters: a domain filter that keeps only entities of the predicted domain, and a hub filter that skips entities with degree above the 99th percentile (degree > 16, 126 entities, e.g. "VA health care" with 99 relations).

Step 4 has no domain classifier, so the predicted domain is the majority domain of the Step 4 best top-5 (hybrid + rewrite + rerank), and the filter is used only when at least 4 of the 5 sections agree. The prediction is right for 94.8% of the questions; it is confident for 471 of them and right for 97.9% of those. The Step 4 retrieval was recomputed from the reranker cache and gives the same section R@5 (67.4%); it is cached for phase 2 in `step4_dev500.json` (not tracked).

Link recall@k is the share of examples where at least one of the top-k entities is mentioned in a gold section (95% Wilson intervals in brackets). Since an entity mentioned in many sections hits more easily, two controls are reported: the fan-out (number of distinct sections the top-10 entities appear in) and a chance level (recall when each example gets the linked entities of a random other example from the same domain, 5 permutations).

## 2. Query variants

Default linker: RRF, domain filter, hub skip.

| Query | R@1 | R@5 | R@10 | Chance R@10 | Fan-out@10 (median) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| raw | 24.2 [20.7, 28.1] | 41.2 [37.0, 45.6] | 47.4 [43.1, 51.8] | 3.6 | 20 |
| rewritten | 29.6 [25.8, 33.7] | 52.2 [47.8, 56.5] | 62.0 [57.7, 66.1] | 5.1 | 22 |
| rewritten + agent | 24.8 [21.2, 28.8] | 49.2 [44.8, 53.6] | 59.4 [55.0, 63.6] | 5.4 | 21 |

The rewrite adds about 15 points at R@10. Only 28% of the raw questions name an entity of the gold section (Step 5 coverage), and the rewrite brings back the referent from the history. Adding the last agent turn doesn't help and lowers R@1 by 5 points, because the previous answer brings in its own entities. Chance recall is 4-7%, so the hits are not just an effect of the fan-out.

## 3. Linker settings (rewritten query)

| Linker | R@1 | R@5 | R@10 | Chance R@10 | Fan-out@10 (median / mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| default (RRF, domain filter, hub skip) | 29.6 | 52.2 | 62.0 | 5.1 | 22 / 23.5 |
| dense only | 27.2 | 49.2 | 59.2 | 5.3 | 21 / 23.0 |
| BM25 only | 32.8 | 50.0 | 59.4 | 5.0 | 20 / 22.5 |
| no domain filter | 29.6 | 51.6 | 61.8 | 4.8 | 21 / 23.3 |
| gold domain (upper bound for the filter) | 30.6 | 54.2 | 63.8 | 5.2 | 22 / 23.3 |
| no hub skip | **33.2** [29.2, 37.4] | **59.6** [55.2, 63.8] | **70.4** [66.3, 74.2] | 7.0 | 29 / 36.5 |
| raw + rewritten fused, hub skip | 26.0 | 47.6 | 57.8 | 4.7 | 21 / 23.3 |
| raw + rewritten fused, no hub skip | 30.6 | 53.2 | 65.0 | 6.2 | 25 / 31.8 |

RRF is better than either generator alone at R@5 and R@10; BM25 alone is best at R@1 (exact name overlap), and dense adds paraphrases. The domain filter is almost neutral (+0.2 at R@10): when the prediction is confident it is nearly always right, and wrong-domain entities rarely reach the top-10 anyway. Even the gold domain would add only about 2 points.

Skipping hubs is the biggest effect, and it's negative. Keeping them adds 8.4 points at R@10 (46 more examples), at the cost of a wider fan-out (median 22 to 29 sections, mean 23.5 to 36.5). Chance recall only goes up to 7.0%, so most of these hits are real: questions about "VA health care" or "Social Security benefits" are about the hub itself.

Fusing raw and rewritten helps on doc-switch turns (section 4) but costs 4-5 points overall.

## 4. Splits

R@10 by turn type:

| Query / linker | Same document (406) | Doc switch (94) | Unanswerable (31) |
| :--- | :---: | :---: | :---: |
| raw | 43.8 [39.1, 48.7] | 62.8 [52.7, 71.9] | 16.1 [7.1, 32.6] |
| rewritten | 63.5 [58.8, 68.1] | 55.3 [45.3, 65.0] | 67.7 [50.1, 81.4] |
| rewritten + agent | 63.3 [58.5, 67.8] | 42.6 [33.0, 52.6] | 80.6 [63.7, 90.8] |
| rewritten, no hub skip | 72.2 [67.6, 76.3] | 62.8 [52.7, 71.9] | 80.6 [63.7, 90.8] |
| raw + rewritten, no hub skip | 64.8 [60.0, 69.3] | 66.0 [55.9, 74.7] | 58.1 [40.8, 73.6] |

Doc-switch turns are the only case where the raw turn beats the rewrite (62.8 vs 55.3). A turn that opens a new topic usually names it, while the rewrite tends to pull the previous topic back in; the agent turn makes it worse (42.6). Fusing raw and rewritten recovers the switch turns (66.0) but loses on same-document turns. With 94 switch turns these differences are within the intervals.

R@10 by domain (125 examples each):

| Query / linker | DMV | SSA | StudentAid | VA |
| :--- | :---: | :---: | :---: | :---: |
| raw | 52.0 | 42.4 | 50.4 | 44.8 |
| rewritten | 65.6 | 55.2 | 67.2 | 60.0 |
| rewritten + agent | 60.0 | 56.0 | 62.4 | 59.2 |
| rewritten, no hub skip | 68.8 | 68.8 | 76.0 | 68.0 |

SSA gains most from keeping hubs (+13.6): its questions name broad entities ("Social Security benefits", "disability benefits") and many of them are hubs. SSA is also the weakest domain at R@1 (17.6% with hub skip), because its entity names are long clauses that overlap with many questions.

## 5. Errors

With the rewritten query and hubs kept there are 148 misses at R@10.

* 17 of them (11%) have no entity in the gold section at all, so they are an extraction problem.
* In most of the others the linker finds entities on the right topic but they are different nodes from the ones in the gold section, e.g. "disability benefits" and "enough Social Security credits at this time to qualify" against "monthly disability benefit" and "enough credits", or "lose eligibility for federal student aid" against "regaining eligibility". Long clause-like names and conservative entity resolution split one concept into several nodes. Going one hop through the relations, or scoring sections by entity similarity instead of identity, could recover some of them.
* Some turns have no content words at all ("do not").
* Some gold sections list many items (e.g. the REAL ID document list): the linker finds "REAL ID", but the entities of the gold section are the listed documents.

The entity that hits first is a Service in 210 cases, a Requirement in 65, a Document in 28, an Outcome in 20 and another type in 29.

## 6. Cost

Linking needs no LLM calls besides the Step 4 rewrite (0.87 calls per question, only for turns with history). Encoding the query with bge-small takes about 6 ms (batched, CPU) and linking over 14,731 entities about 8-9 ms (15 ms with the agent turn). Exporting the entities from Neo4j and embedding the surface forms takes under a minute and is done once.

## 7. Decisions for phase 2

1. Use the Step 4 rewrite as the query, without the agent turn. The raw turn would only be fused in for doc-switch turns if phase 2 showed a QA gain there.
2. Keep hubs in linking: skipping them costs 8 points and the p99 cap is too aggressive. Their fan-out is handled in section scoring instead, by down-weighting an entity by the number of sections it appears in, and hubs are not expanded through relations.
3. Keep the domain filter where it's allowed, since it is nearly neutral and cheap. (In phase 2 it was finally used only in the hybrid retriever, because the predicted domain comes from Step 4.)
4. Pass the top-10 entities to the retrievers; the top-1 is right only for about a third of the questions.
5. Link recall@10 (70%) is close to the Step 4 section R@5 (67.4%), but a linked entity reaches 29 sections at the median. So ranking the sections, not linking, will decide how graph retrieval compares with Step 4.

Limitations: dev-500 only, and differences under about 6 points between settings are within the intervals; a hit counts any mention in the gold section, not that the entity is the one the question is about; the domain threshold (0.8) and the hub percentile (p99) were fixed in advance, not tuned.
