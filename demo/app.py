"""Local demo chat for the final system (MultiDoc2Dial, passages + graph facts, gpt-5.4-nano).

    python demo/app.py                              # http://127.0.0.1:7860
    python demo/app.py --share --auth user:pass     # temporary public link, password required

Keys are read from .env by the LLM client; they are never printed or logged.
"""
import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import ABSTAIN, SYSTEMS, Pipeline, display_title  # noqa: E402

import gradio as gr  # noqa: E402

from src.data.loader import load_qa_pairs  # noqa: E402

N_EXAMPLES, SEED = 4, 42


def example_questions() -> List[str]:
    """First turns of validation dialogues, answerable, one per domain (seed 42)."""
    by_dom = defaultdict(list)
    for ex in load_qa_pairs(split="validation", max_examples=None):
        if not ex["dialogue_history"] and not ex.get("is_unanswerable") and 25 <= len(ex["question"]) <= 120:
            by_dom[ex["domain"]].append(ex["question"].strip())
    rng = random.Random(SEED)
    return [rng.choice(sorted(by_dom[d])) for d in sorted(by_dom)][:N_EXAMPLES]


def sources_md(res: Dict[str, Any]) -> str:
    if not res["sources"]:
        return ""
    head = "Sources" if res["cite"] else "Source (best match, no citation asked)"
    items = "; ".join(f"{s['title']} — {s['section']}" if s["section"] else s["title"] for s in res["sources"])
    return f"\n\n<sub>**{head}:** {items}</sub>"


def passages_md(res: Dict[str, Any]) -> str:
    rows = ["| # | Score | Section |", "| --- | --- | --- |"]
    for r in res["ranking"]:
        sec = display_title(r["title"]) + (f" — {r['section_title']}" if r.get("section_title") else "")
        rows.append(f"| {r['rank']} | {r['score']:.3f} | {sec.replace('|', chr(92) + '|')} |")  # titles contain "|"
    texts = "\n".join(f"<details><summary>[{r['rank']}] text</summary>\n\n{r['text']}\n\n</details>" for r in res["ranking"])
    return "\n".join(rows) + "\n\n" + texts


def facts_md(res: Dict[str, Any], pipe: Pipeline) -> str:
    if res["system"] == "P":
        return "_P uses no graph facts._"
    if not res["facts"]:
        return "_No facts for the linked entities._"
    ents = pipe.kg.entities
    lines = []
    for f in res["facts"]:
        a, b = ents[f["source"]], ents[f["target"]]
        line = f"**F{f['rank']}** {a['name']} ({a['type']}) —{f['relation']}→ {b['name']} ({b['type']})"
        if f["evidence"]:
            line += f"<br><sub>“{f['evidence'][0]['text']}”</sub>"
        lines.append(line)
    return "\n\n".join(lines)


def cost_md(res: Dict[str, Any], total: Dict[str, float]) -> str:
    rows = ["| Call | In | Cached | Out | USD |", "| --- | --- | --- | --- | --- |"]
    for c in res["calls"]:
        rows.append(f"| {c['call']} | {c['input_tokens'] or 0:,} | {c['cached_tokens'] or 0:,} | "
                    f"{c['output_tokens'] or 0:,} | {c['usd']:.5f} |")
    t_in = sum(c["input_tokens"] or 0 for c in res["calls"])
    t_out = sum(c["output_tokens"] or 0 for c in res["calls"])
    t_cached = sum(c["cached_tokens"] or 0 for c in res["calls"])
    rows.append(f"| **This turn** | {t_in:,} | {t_cached:,} | {t_out:,} | **{res['usd']:.5f}** |")
    times = ", ".join(f"{k} {v:.1f} s" for k, v in res["times"].items())
    return ("\n".join(rows) + f"\n\n**Conversation:** {int(total['turns'])} turns, {int(total['in']):,} in ({int(total.get('cached', 0)):,} cached) / "
            f"{int(total['out']):,} out tokens, USD {total['usd']:.4f}\n\n**Time:** {times} "
            f"(total {sum(res['times'].values()):.1f} s)\n\n<sub>gpt-5.4-nano list prices, USD per 1M tokens: "
            f"0.20 input, 0.02 cached input, 1.25 output. Cached input is the start of the prompt that the API "
            f"reuses from an earlier call, so the cost is not proportional to the input tokens.</sub>")


def build(pipe: Pipeline) -> gr.Blocks:
    def respond(message: str, chat: List[Dict], history: List[Dict], total: Dict, system: str, cite: bool):
        message = (message or "").strip()
        if not message:
            yield chat, history, total, "", gr.skip(), gr.skip(), gr.skip(), gr.skip()
            return
        chat = chat + [{"role": "user", "content": message}, {"role": "assistant", "content": "…"}]
        yield chat, history, total, "", gr.skip(), gr.skip(), gr.skip(), gr.skip()
        try:
            res = pipe.answer(message, history, system=system, cite=cite)
        except Exception as e:  # API errors carry no credentials (src.llm.client strips them)
            chat[-1] = {"role": "assistant", "content": f"_Error: {e}_"}
            yield chat, history, total, "", gr.skip(), gr.skip(), gr.skip(), gr.skip()
            return
        chat[-1] = {"role": "assistant", "content": res["answer"] + sources_md(res)}
        history = history + [{"role": "user", "utterance": message}, {"role": "agent", "utterance": res["answer"]}]
        total = {"turns": total["turns"] + 1, "usd": total["usd"] + res["usd"],
                 "in": total["in"] + sum(c["input_tokens"] or 0 for c in res["calls"]),
                 "out": total["out"] + sum(c["output_tokens"] or 0 for c in res["calls"]),
                 "cached": total.get("cached", 0) + sum(c["cached_tokens"] or 0 for c in res["calls"])}
        rw = res["rewritten"] if res["rewritten"] != message else f"{res['rewritten']}  _(unchanged)_"
        yield (chat, history, total, "", f"**{SYSTEMS[system]}**\n\n{rw}", passages_md(res), facts_md(res, pipe),
               cost_md(res, total))

    def new_conversation():
        return [], [], {"turns": 0, "usd": 0.0, "in": 0, "out": 0, "cached": 0}, "", "", "", "", ""

    with gr.Blocks(title="MultiDoc2Dial RAG + KG demo") as demo:
        gr.Markdown("## Government services assistant")
        history = gr.State([])
        total = gr.State({"turns": 0, "usd": 0.0, "in": 0, "out": 0, "cached": 0})
        with gr.Row():
            with gr.Column(scale=3):
                with gr.Row():
                    system = gr.Radio(list(SYSTEMS), value="E", label="System",
                                      info="P passages · E passages + 30 graph facts · V1 passages + top 10 facts")
                    cite = gr.Checkbox(value=True, label="Citations")
                chat = gr.Chatbot(height=520, label="Chat")
                msg = gr.Textbox(placeholder="Ask about a government service…", label="Your message", lines=1)
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    clear = gr.Button("New conversation")
                gr.Examples(example_questions(), inputs=msg, label="Examples (first turns from the validation set)")
            with gr.Column(scale=2):
                with gr.Accordion("Rewritten query", open=True):
                    rw = gr.Markdown()
                with gr.Accordion("Top 5 passages", open=False):
                    psg = gr.Markdown(max_height=320)
                with gr.Accordion("Graph facts used", open=False):
                    fct = gr.Markdown(max_height=320)
                with gr.Accordion("Tokens and cost", open=True):
                    cst = gr.Markdown()
        outs = [chat, history, total, msg, rw, psg, fct, cst]
        ins = [msg, chat, history, total, system, cite]
        msg.submit(respond, ins, outs)
        send.click(respond, ins, outs)
        clear.click(new_conversation, None, outs)
    return demo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--share", action="store_true", help="temporary public link (requires --auth)")
    ap.add_argument("--auth", help="user:password for the login page")
    ap.add_argument("--port", type=int, default=7860)
    args = ap.parse_args()
    auth = None
    if args.auth:
        user, sep, pw = args.auth.partition(":")
        if not (sep and user and pw):
            sys.exit("--auth must be user:password")
        auth = (user, pw)
    if args.share and not auth:
        sys.exit("--share makes the demo public and spends your API credit: start it with --auth user:password")
    pipe = Pipeline()
    build(pipe).launch(server_name="127.0.0.1", server_port=args.port, share=args.share, auth=auth)


if __name__ == "__main__":
    main()
