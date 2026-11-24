"""Local demo chat for the final system (MultiDoc2Dial, passages + graph facts, gpt-5.4-nano).

    python demo/app.py                              # http://127.0.0.1:7860
    python demo/app.py --share --auth user:pass     # temporary public link, password required

Keys are read from .env by the LLM client; they are never printed or logged.
"""
import argparse
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import ABSTAIN, SYSTEMS, Pipeline, display_title, stream_view  # noqa: E402
import tts  # noqa: E402

import gradio as gr  # noqa: E402

from src.data.loader import load_qa_pairs  # noqa: E402

N_EXAMPLES, SEED = 4, 42
LATE_TIMEOUT = 130  # s to wait for a dropped G2 call (the API timeout is 120 s)


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
        if c.get("pending"):  # a dropped G2 call that has not completed yet
            rows.append(f"| {c['call']} | … | … | … | … |")
            continue
        rows.append(f"| {c['call']} | {c['input_tokens'] or 0:,} | {c['cached_tokens'] or 0:,} | "
                    f"{c['output_tokens'] or 0:,} | {c['usd']:.5f} |")
    t_in = sum(c["input_tokens"] or 0 for c in res["calls"])
    t_out = sum(c["output_tokens"] or 0 for c in res["calls"])
    t_cached = sum(c["cached_tokens"] or 0 for c in res["calls"])
    rows.append(f"| **This turn** | {t_in:,} | {t_cached:,} | {t_out:,} | **{res['usd']:.5f}** |")
    times = ", ".join(f"{k} {v:.1f} s" for k, v in res["times"].items())
    total_s = sum(res["times"].values())
    t = res.get("tts") or {}
    since = [f"{k} {t[v]:.1f} s" for k, v in (("first token", "first_token"), ("first audio", "first_audio"),
                                               ("voice done", "seconds")) if t.get(v) is not None]
    if since:  # measured from the moment Send was pressed; the voice is not in the total
        times += " · from Send: " + ", ".join(since)
    return ("\n".join(rows) + f"\n\n**Conversation:** {int(total['turns'])} turns, {int(total['in']):,} in ({int(total.get('cached', 0)):,} cached) / "
            f"{int(total['out']):,} out tokens, USD {total['usd']:.4f}\n\n**Time:** {times} "
            f"(total {total_s:.1f} s)\n\n<sub>gpt-5.4-nano list prices, USD per 1M tokens: "
            f"0.20 input, 0.02 cached input, 1.25 output. Cached input is the start of the prompt that the API "
            f"reuses from an earlier call, so the cost is not proportional to the input tokens.</sub>")


def add_calls(total: Dict[str, float], calls: List[Dict[str, Any]], turn: int = 0) -> Dict[str, float]:
    """Conversation totals with the tokens and cost of `calls` added."""
    return {"turns": total["turns"] + turn, "usd": total["usd"] + sum(c["usd"] for c in calls),
            "in": total["in"] + sum(c["input_tokens"] or 0 for c in calls),
            "out": total["out"] + sum(c["output_tokens"] or 0 for c in calls),
            "cached": total.get("cached", 0) + sum(c["cached_tokens"] or 0 for c in calls)}


def build(pipe: Pipeline) -> gr.Blocks:
    def ui(chat: List[Dict], panels=None, cost=None, audio=None, info=None, mp3=None, total=None):
        """One update of the outputs; what is not given stays as it is."""
        keep = gr.skip()
        return ((chat, keep, keep if total is None else total, keep) + (panels or (keep,) * 3) +
                tuple(keep if v is None else v for v in (cost, audio, info, mp3)))

    def respond(message: str, chat: List[Dict], history: List[Dict], total: Dict, system: str, cite: bool,
                voice: bool, voice_model: str):
        t_send = time.time()
        message = (message or "").strip()
        if not message:
            yield ui(chat)
            return
        chat = chat + [{"role": "user", "content": message}, {"role": "assistant", "content": "…"}]
        yield (chat, history, total, "") + (gr.skip(),) * 4 + (None, "", None)
        vs: Optional[tts.VoiceStream] = None
        raw, fed, abstain, first_token, last_ui, voice_err, panels, res = "", 0, None, None, 0.0, "", None, None

        def feed_sentences(text: str, finished: bool) -> None:
            nonlocal vs, fed
            vs = vs or tts.VoiceStream(voice_model, start=t_send)
            for part in tts.complete_sentences(text, finished)[fed:]:
                vs.feed(part)
                fed += 1

        try:
            for kind, val in pipe.answer_stream(message, history, system=system, cite=cite):
                if kind == "prepared":
                    rw = val["rewritten"] if val["rewritten"] != message else f"{val['rewritten']}  _(unchanged)_"
                    panels = (f"**{SYSTEMS[system]}**\n\n{rw}", passages_md(val), facts_md(val, pipe))
                    yield ui(chat, panels)
                elif kind == "g0":
                    abstain = val
                    if abstain:  # the streamed G2 text is dropped
                        chat[-1] = {"role": "assistant", "content": ABSTAIN}
                        yield ui(chat)
                elif kind == "delta" and abstain is not True:
                    raw += val
                    first_token = first_token or time.time() - t_send
                    shown = stream_view(raw, cite)
                    chat[-1] = {"role": "assistant", "content": shown or "…"}
                    chunks: List[bytes] = []
                    if voice and abstain is False:  # the voice starts only once G0 has not abstained
                        try:
                            feed_sentences(shown, False)
                            chunks = vs.ready()
                        except tts.TTSError as e:
                            voice, voice_err = False, str(e)
                    for c in chunks:
                        yield ui(chat, audio=c)
                    if not chunks and time.time() - last_ui > 0.05:
                        yield ui(chat)
                    last_ui = time.time()
                elif kind == "done":
                    res = val
        except Exception as e:  # API errors carry no credentials (src.llm.client strips them)
            if vs:
                vs.close()
            chat[-1] = {"role": "assistant", "content": f"_Error: {e}_"}
            yield ui(chat)
            return
        chat[-1] = {"role": "assistant", "content": res["answer"] + sources_md(res)}
        history = history + [{"role": "user", "utterance": message}, {"role": "agent", "utterance": res["answer"]}]
        late = res["late"]  # dropped G2 calls still running: their cost is added when they complete
        total = add_calls(total, [c for c in res["calls"] if c not in late], turn=1)
        res["tts"] = {"first_token": first_token}
        info = "_Generating audio…_" if voice else (f"_Voice error: {voice_err}_" if voice_err else "")
        yield (chat, history, total, "") + panels + (cost_md(res, total), gr.skip(), info, None)
        if voice:
            # The text is final; the sentences still missing (all of them after an abstention) go to the voice now.
            try:
                feed_sentences(res["answer"], True)
                for chunk in vs.drain():
                    yield ui(chat, audio=chunk)
            except tts.TTSError as e:
                voice_err = str(e)
        if vs:
            st = vs.close()
            res["tts"] = {"first_token": first_token, "first_audio": st["first_audio"], "seconds": st["seconds"]}
            if voice_err:
                yield ui(chat, cost=cost_md(res, total), info=f"_Voice error: {voice_err}_", mp3=st["path"])
            elif voice:
                credits = f" · {st['credits']:,} credits" if st["credits"] is not None else ""
                yield ui(chat, cost=cost_md(res, total), mp3=st["path"],
                         info=f"<sub>{st['model']} · {st['chars']:,} characters{credits} · {st['sentences']} sentences · "
                              f"first audio {st['first_audio']:.1f} s from Send</sub>")
        for c in late:  # the answer is out; only the cost of the dropped G2 call is still missing
            c["settled"].wait(timeout=LATE_TIMEOUT)
        done = [c for c in late if c["settled"].is_set()]
        if done:
            total = add_calls(total, done)
            res["usd"] += sum(c["usd"] for c in done)
            yield ui(chat, cost=cost_md(res, total), total=total)

    def new_conversation():
        return [], [], {"turns": 0, "usd": 0.0, "in": 0, "out": 0, "cached": 0}, "", "", "", "", "", None, "", None

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
                with gr.Row():
                    voice = gr.Checkbox(value=tts.enabled(), interactive=tts.enabled(), label="Voice (ElevenLabs)",
                                        info=None if tts.enabled() else "set ELEVENLABS_API_KEY in .env to enable")
                    voice_model = gr.Dropdown(tts.MODELS, value=tts.default_model(), label="Voice model",
                                              allow_custom_value=True, interactive=tts.enabled())
                chat = gr.Chatbot(height=520, label="Chat")
                audio = gr.Audio(label="Answer audio", streaming=True, autoplay=True, interactive=False)
                with gr.Row():
                    audio_info = gr.Markdown()
                    mp3 = gr.DownloadButton("Download mp3", size="sm", scale=0)
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
        outs = [chat, history, total, msg, rw, psg, fct, cst, audio, audio_info, mp3]
        ins = [msg, chat, history, total, system, cite, voice, voice_model]
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
    # Gradio serves only files under allowed paths; the answer audio is written to demo/logs/tts/.
    build(pipe).launch(server_name="127.0.0.1", server_port=args.port, share=args.share, auth=auth,
                       allowed_paths=[str(tts.AUDIO_DIR)])


if __name__ == "__main__":
    main()
