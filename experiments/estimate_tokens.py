"""Token estimates per turn and per conversation for each system, from the stored prompts and
answers (token usage of the generation and rewrite calls was not recorded).

Tokens are counted with tiktoken o200k_base. Input = generation prompt (+ rewrite prompt for the
systems that use the rewritten query), output = answer (+ rewritten query). Reasoning tokens of
the model are billed as output but are not visible, so the output figures are a lower bound.

    python experiments/estimate_tokens.py [--split validation|dev500|test]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.kg_rag.queries import load_step4
from src.rag.query_rewriter import REWRITE_PROMPT, _format_history

SYSTEMS = {
    # file: (label, uses the rewritten query)
    "llm_baseline": ("LLM only", False),
    "oracle_context_v2": ("Oracle", False),
    "rag_rewrite_rerank_v2": ("Passage RAG (best)", True),
    "kg_sections": ("A: graph sections", True),
    "kg_hybrid": ("C: graph + passages, reranked", True),
    "kg_rerank": ("D: graph candidates, reranked", True),
    "kg_facts": ("B: graph facts", True),
    "step4_plus_facts": ("E: passages + facts", True),
    "step4_plus_random_facts": ("E-random", True),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="validation", choices=["validation", "dev500", "test"])
    args = parser.parse_args()
    enc = tiktoken.get_encoding("o200k_base")
    n = lambda s: len(enc.encode(s or "", disallowed_special=()))

    step4 = load_step4(args.split)
    rewrite_in, rewrite_out = {}, {}
    for ex in step4["examples"]:
        rec = step4["records"][ex["example_id"]]
        if ex.get("dialogue_history"):
            rewrite_in[ex["example_id"]] = n(REWRITE_PROMPT.format(history=_format_history(ex["dialogue_history"]),
                                                                   question=ex["question"]))
            rewrite_out[ex["example_id"]] = n(rec["rewritten"])

    res_dir = PROJECT_ROOT / "experiments" / "results" / ("dev_500" if args.split == "dev500" else args.split)
    out = {"split": args.split, "tokenizer": "o200k_base", "systems": {}}
    for name, (label, rewrite) in SYSTEMS.items():
        path = res_dir / f"{name}.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        per_dialogue = defaultdict(lambda: [0, 0])
        tin, tout, calls = [], [], []
        for r in rows:
            i, o, c = n(r["prompt"]), n(r["model_answer"]), 1
            if rewrite and r["example_id"] in rewrite_in:
                i += rewrite_in[r["example_id"]]
                o += rewrite_out[r["example_id"]]
                c += 1
            tin.append(i); tout.append(o); calls.append(c)
            per_dialogue[r["dialogue_id"]][0] += i
            per_dialogue[r["dialogue_id"]][1] += o
        d = np.array(list(per_dialogue.values()))
        out["systems"][name] = {
            "label": label, "turns": len(rows), "conversations": len(per_dialogue),
            "calls_per_turn": float(np.mean(calls)),
            "in_per_turn": float(np.mean(tin)), "out_per_turn": float(np.mean(tout)),
            "in_per_conversation": float(d[:, 0].mean()), "out_per_conversation": float(d[:, 1].mean()),
            "in_total": int(sum(tin)), "out_total": int(sum(tout)),
        }
        s = out["systems"][name]
        print(f"{label:32} in/turn {s['in_per_turn']:7.0f}  out/turn {s['out_per_turn']:5.0f}  "
              f"in/conv {s['in_per_conversation']:8.0f}  out/conv {s['out_per_conversation']:6.0f}")
    dest = PROJECT_ROOT / "docs" / "schematic" / f"token_estimates_{args.split}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"-> {dest}")


if __name__ == "__main__":
    main()
