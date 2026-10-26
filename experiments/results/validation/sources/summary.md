# Sources per answer (validation)

Final system unchanged: passages + 30 graph facts (E), gpt-5.4-nano, G2 + abstain(G0). Validation only; the test split was not used. A source is a document section; it is gold when it holds the grounding span of the reference answer. Refusals get no source.

## A. Post-hoc attribution (no LLM calls)

For each cached answer, the candidate sections are the 5 passages and the evidence sections of the facts in the prompt; they are ranked by the share of the answer's tokens (F1 normalisation) that their text in the prompt contains.

| Answered questions | n | top-1 source is gold | gold in the top 2 | gold anywhere in the context (upper bound) |
| :--- | ---: | :---: | :---: | :---: |
| all answered | 4,181 | 39.5% | 54.5% | 73.2% |
| passages hit | 2,732 | 59.7% | 82.0% | 100.0% |
| passages miss | 1,449 | 1.4% | 2.7% | 22.6% |
| answerable | 4,008 | 39.7% | 54.8% | 73.1% |

4,181 of 4,427 questions are answered. 'Passages hit': a gold section is among the 5 passages.

## B. Citations by the generator

The G2 prompt asks the model to end its answer with the numbers of the passages and facts it used ([2], [F7]); facts are numbered [F1]-[F30] in the prompt and each maps to the section of its evidence quote. G0 (the abstention decision) is unchanged. Citations are stripped before computing F1. Rule: full validation only if F1 does not drop by more than 0.3 points on dev-500.

| | dev-500 | full validation |
| :--- | :---: | :---: |
| F1 with citations / without | 31.2 / 30.4 | 28.3 / 28.0 |
| Δ F1, all [95% CI] | +0.8 [-0.2, 1.9] | +0.3 [0.0, 0.6] |
| Δ F1, answerable [95% CI] | +0.4 [-0.4, 1.3] | +0.3 [0.0, 0.5] |
| false abstention with / without | 4.7% / 4.9% | 4.4% / 4.6% |
| answered questions | 465 | 4,189 |
| no citation | 0.9% | 0.9% |
| at least one invalid citation number | 2.4% | 1.8% |
| first cited source is gold | 43.6% | 42.2% |
| any cited source is gold | 52.9% | 52.2% |
| first cited source is gold, passages hit / miss | 62.9% / 1.4% | 63.4% / 2.6% |
| distinct cited sections per answer | 1.8 | 1.8 |
| extra tokens per G2 call, input / output | 50 / 6.1 | 50 / 6.4 |

Precision is over the answered questions with at least one valid citation. Tokens are counted from the prompts and answers (o200k_base); every call is also in the usage log (call type G2-cite).

## C. Demo examples

Five answered validation turns, drawn with seed 42: [demo_examples.md](demo_examples.md).

## Findings

* Asking for citations costs nothing in quality: F1 is +0.3 points on the full split, and false abstention slightly lower. It adds 50 input and about 6 output tokens per G2 call.
* The first cited source is a gold section in 42.2% of the answered questions, a little above post-hoc attribution (39.5%), and any cited source in 52.2%. Answers cite 1.8 sections on average; 1% cite nothing and 2% contain a number that is not in the prompt.
* Source precision is bounded by retrieval: when a gold section is among the passages the first citation is gold in 63.4% of the cases, when it is not, in 2.6%. A gold section reaches the prompt at all for 73.2% of the answered questions; on retrieval misses it can only come through a graph fact (22.6% of them).
* For a demo, both work: the cited sections can be shown directly, and the post-hoc overlap is about as precise (39.5% against 42.2%) with no extra tokens.
