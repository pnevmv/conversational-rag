# Step 7: final systems on the test split

Test split of MultiDoc2Dial, 4335 questions (241 unanswerable), run once with the systems frozen on validation (plans/step7-graph-rag.md, experiments/results/validation/graph_rag/decisions.md); nothing was tuned on the test split. All systems use gpt-5.4-nano with the dialogue history and the abstention decision of the prompt without history (G2 + abstain(G0)), the same rewrites and passages, and differ only in the graph facts. Δ: paired bootstrap difference with its 95% interval. Input tokens per turn: generator calls only (G0 always, G2 when G0 does not abstain), counted from the prompts (o200k_base); the rewrite is the same for all.

| System | F1 all | answerable | unanswerable | abstain recall / false abstention | input tokens / turn |
| :--- | :---: | :---: | :---: | :---: | :---: |
| P: passages | 27.6 | 27.5 | 28.4 | 27.4 / 6.3 | 2,324 (-59% vs E) |
| E: passages + 30 facts | 28.2 | 28.4 | 24.1 | 23.7 / 4.4 | 5,621 (+0% vs E) |
| V1: passages + 10 facts | 27.8 | 28.1 | 22.3 | 21.6 / 4.5 | 3,608 (-36% vs E) |

| Comparison | Δ all | Δ answerable | Δ unanswerable |
| :--- | :---: | :---: | :---: |
| V1 vs P | +0.2 [-0.2, 0.6] | +0.6 [0.3, 0.9] | -6.0 [-11.4, -0.9] |
| E vs P | +0.6 [0.1, 1.0] | +0.9 [0.6, 1.2] | -4.3 [-10.2, 1.1] |
| V1 vs E | -0.4 [-0.7, 0.0] | -0.3 [-0.6, -0.0] | -1.7 [-6.3, 3.6] |
## Result

* Passages + 30 graph facts (E) remain the best system on the test split: +0.6 F1 over passages on all questions and +0.9 on answerable ones, both significant, as on validation (+0.5 and +0.6).
* The filtered variant V1 (10 facts by cross-encoder score), which matched E on validation with 35% fewer input tokens, is slightly worse than E on test: −0.4 on all questions ([−0.7, 0.0]) and −0.3 on answerable ones ([−0.6, −0.0]). It still gains 0.6 over passages on answerable questions with 36% fewer input tokens than E.
* The graph facts lower F1 on the 241 unanswerable questions (fewer abstentions), with wide intervals.
* Step 7 did not find a better way to use the graph than appending the one-hop facts of the linked entities; the filtered selection is the cheaper option at a small cost in F1.
