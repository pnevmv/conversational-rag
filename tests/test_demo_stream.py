"""Streamed G2 in demo/pipeline.py and the voice feed in demo/app.py (fake LLM, fake ElevenLabs, no network)."""
import sys
import threading
import time
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))
import app  # noqa: E402
import pipeline  # noqa: E402
import tts  # noqa: E402
from pipeline import ABSTAIN, Pipeline, stream_view  # noqa: E402

USAGE = {"input_tokens": 100, "cached_tokens": 0, "output_tokens": 10, "reasoning_tokens": 0}
ANSWER = "You can apply online at the portal. Then you wait for the letter. [2]"


class FakeLLM:
    """G0 answers whole after g0_delay; G2 streams its text in 8-character deltas, one every `tick` seconds."""

    def __init__(self, g0, g2, g0_delay=0.0, tick=0.0, fail_g2=False):
        self.out, self.g0_delay, self.tick, self.fail_g2 = {"G0": g0, "G2": g2}, g0_delay, tick, fail_g2

    def generate_with_usage(self, prompt, model=None, meta=None):
        time.sleep(self.g0_delay if meta["call_type"] == "G0" else 0)
        return self.out[meta["call_type"]], dict(USAGE)

    def generate_stream_with_usage(self, prompt, model=None, meta=None):
        text = self.out[meta["call_type"]]
        for i in range(0, len(text), 8):
            time.sleep(self.tick)
            yield text[i:i + 8]
            if self.fail_g2 and i > 8:
                raise RuntimeError("LLM API request failed: boom")
        yield dict(USAGE)


def make_pipe(llm, same_prompt=False):
    pipe = Pipeline.__new__(Pipeline)
    pipe.client = llm
    prompts = {"G0": "a", "G2": "a" if same_prompt else "b"}
    pipe.prepare = lambda q, h, system, cite: {
        "question": q, "system": system, "cite": cite, "rewritten": q, "ranking": [], "facts": [], "context": "",
        "prompts": prompts, "calls": [], "times": {}}
    pipe.sources = lambda *a, **k: []
    return pipe


def events(pipe):
    return list(pipe.answer_stream("How do I apply?", [], system="P", cite=True))


def test_stream_view_holds_back_unclosed_bracket():
    assert stream_view("You can apply online [") == "You can apply online"
    assert stream_view("You can apply online [2, F") == "You can apply online"
    assert stream_view("You can apply online [2]") == "You can apply online"
    assert stream_view("Yes [2] and no [F3, 4]") == "Yes and no"
    assert stream_view("Use form [A", cite=False) == "Use form [A"


def test_streamed_answer_equals_non_streamed_one():
    for g0, g2 in (("Yes.", ANSWER), (ABSTAIN, ANSWER)):
        ev = events(make_pipe(FakeLLM(g0, g2)))
        done = ev[-1][1]
        pipe = make_pipe(FakeLLM(g0, g2))
        st = pipe.prepare("How do I apply?", [], "P", True)
        ref = pipe.finish(st, pipe.generate(st["prompts"], "P", st["calls"], st["times"]))
        assert (done["raw_answer"], done["answer"], done["abstained"]) == (ref["raw_answer"], ref["answer"], ref["abstained"])
        for c in done["calls"] + ref["calls"]:
            if "settled" in c:
                assert c["settled"].wait(2)
        assert [c["call"] for c in done["calls"]] == [c["call"] for c in ref["calls"]]
        assert done["usd"] == pytest.approx(ref["usd"])
    assert ev[-1][1]["answer"] == ABSTAIN


def test_deltas_come_before_g0_and_before_done():
    ev = events(make_pipe(FakeLLM("Yes.", ANSWER, g0_delay=0.3, tick=0.02)))
    kinds = [k for k, _ in ev]
    assert kinds[0] == "prepared" and kinds[-1] == "done" and kinds.count("g0") == 1
    assert "".join(v for k, v in ev if k == "delta") == ANSWER
    assert kinds.index("delta") < kinds.index("g0")  # G0 was still running while G2 streamed
    assert ev[kinds.index("g0")][1] is False
    assert ev[-1][1]["raw_answer"] == ANSWER and "G0+G2" in ev[-1][1]["times"]


def test_abstain_after_streaming_drops_text_and_counts_discarded_g2():
    ev = events(make_pipe(FakeLLM(ABSTAIN, ANSWER, g0_delay=0.3, tick=0.02)))
    kinds = [k for k, _ in ev]
    assert kinds.index("delta") < kinds.index("g0") and ev[kinds.index("g0")][1] is True
    done = ev[-1][1]
    assert done["answer"] == ABSTAIN and done["abstained"] and done["sources"] == []
    assert [c["call"] for c in done["calls"]] == ["G0", "G2 (discarded)"] and done["usd"] > 0 and done["late"] == []


def test_abstention_is_returned_without_waiting_for_g2_and_its_cost_settles_later():
    t = time.time()
    ev = events(make_pipe(FakeLLM(ABSTAIN, ANSWER * 2, tick=0.1)))  # G2 streams for about 1.8 s
    assert time.time() - t < 1.0
    kinds = [k for k, _ in ev]
    assert kinds[-2:] == ["g0", "done"] and ev[-2][1] is True
    done = ev[-1][1]
    assert done["answer"] == ABSTAIN and done["usd"] > 0 and "G0" in done["times"]  # G0's cost only
    late = done["late"][0]
    assert late["call"] == "G2 (discarded, pending)" and late["input_tokens"] is None
    g0_usd = done["usd"]
    assert late["settled"].wait(5) and late["call"] == "G2 (discarded)" and late["usd"] > 0 and not late["pending"]
    assert done["usd"] == g0_usd  # the turn's own sum is not changed behind the caller's back


def test_same_prompt_streams_one_call_and_decides_at_the_end():
    ev = events(make_pipe(FakeLLM("Yes, online.", "unused"), same_prompt=True))
    kinds = [k for k, _ in ev]
    assert kinds.index("g0") > max(i for i, k in enumerate(kinds) if k == "delta")
    assert ev[-1][1]["answer"] == "Yes, online." and [c["call"] for c in ev[-1][1]["calls"]] == ["G0"]
    ev = events(make_pipe(FakeLLM(ABSTAIN, "unused"), same_prompt=True))
    assert ev[-1][1]["answer"] == ABSTAIN


def test_g2_failure_matters_only_when_g2_is_the_answer():
    assert events(make_pipe(FakeLLM(ABSTAIN, ANSWER, g0_delay=0.2, fail_g2=True)))[-1][1]["answer"] == ABSTAIN
    with pytest.raises(RuntimeError, match="boom"):
        events(make_pipe(FakeLLM("Yes.", ANSWER, fail_g2=True)))


# ---- the UI feeds complete sentences to the voice while the text is still streaming
class FakeEleven:
    def __init__(self):
        self.calls = []
        self.text_to_speech = self.with_raw_response = self

    @contextmanager
    def convert(self, voice_id, **kw):
        self.calls.append(kw)

        class R:
            data, headers = iter([b"A:" + kw["text"].encode()]), {"character-cost": "5"}
        yield R()


class ScriptedPipe:
    """answer_stream that writes ANSWER word by word and records when it ends."""

    def __init__(self, g0_abstains=False, late_usd=0.0):
        self.g0_abstains, self.late_usd, self.done_at = g0_abstains, late_usd, None

    def answer_stream(self, message, history, system="E", cite=True):
        st = {"system": system, "rewritten": message, "ranking": [], "facts": [], "sources": [], "cite": cite,
              "calls": [], "times": {"rewrite": 0.0}, "usd": 0.0}
        yield "prepared", st
        yield "g0", self.g0_abstains
        for w in ANSWER.split(" "):
            time.sleep(0.05)
            yield "delta", w + " "
        time.sleep(0.4)  # G2 still finishing: the first sentences must already be with the voice
        self.done_at = time.time()
        raw = ABSTAIN if self.g0_abstains else ANSWER
        late = []
        if self.late_usd:  # a dropped G2 call that completes 0.3 s after the answer
            call = {"call": "G2 (discarded, pending)", "pending": True, "usd": 0.0, "input_tokens": None,
                    "cached_tokens": None, "output_tokens": None, "settled": threading.Event()}
            late = [call]

            def settle():
                call.update(call="G2 (discarded)", pending=False, usd=self.late_usd, input_tokens=100, cached_tokens=0,
                            output_tokens=10)
                call["settled"].set()
            threading.Timer(0.3, settle).start()
        yield "done", {**st, "raw_answer": raw, "answer": pipeline.src_attr.strip_citations(raw), "abstained": self.g0_abstains,
                       "calls": [call for call in late], "late": late}


def run_respond(monkeypatch, tmp_path, pipe):
    eleven = FakeEleven()
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-key")
    monkeypatch.setattr(tts, "_client", eleven)
    monkeypatch.setattr(tts, "_no_context", set())
    monkeypatch.setattr(tts, "VoiceStream", partial(tts.VoiceStream, out_dir=tmp_path / "tts"))
    demo = app.build(pipe)
    respond = next(f.fn for f in demo.fns.values() if f.fn.__name__ == "respond")
    total = {"turns": 0, "usd": 0.0, "in": 0, "out": 0, "cached": 0}
    out = []
    for upd in respond("How do I apply?", [], [], total, "P", True, True, "eleven_flash_v2_5"):
        out.append((time.time(), upd))
    return out, eleven


def audio_chunks(out):
    return [(t, u[8]) for t, u in out if isinstance(u[8], bytes)]


def test_sentences_reach_the_voice_in_order_before_the_text_ends(monkeypatch, tmp_path):
    pipe = ScriptedPipe()
    out, eleven = run_respond(monkeypatch, tmp_path, pipe)
    chunks = audio_chunks(out)
    assert [c for _, c in chunks] == [b"A:You can apply online at the portal.", b"A:Then you wait for the letter."]
    assert chunks[0][0] < pipe.done_at  # the first sentence was heard while the model was still writing
    assert [c.get("previous_text") for c in eleven.calls] == [None, "You can apply online at the portal."]
    chat = [u[0] for _, u in out][-1]
    assert chat[-1]["content"] == "You can apply online at the portal. Then you wait for the letter."
    assert (tmp_path / "tts_usage.jsonl").exists() and len(list((tmp_path / "tts").glob("*.mp3"))) == 1
    assert "first token" in out[-1][1][7] and "first audio" in out[-1][1][7]
    assert "secret-key" not in repr(out)


def test_abstention_replaces_text_and_is_read_after_done(monkeypatch, tmp_path):
    pipe = ScriptedPipe(g0_abstains=True)
    out, eleven = run_respond(monkeypatch, tmp_path, pipe)
    assert [e["content"] for e in [u[0][-1] for _, u in out if u[0] is not None and isinstance(u[0], list)]][-1] == ABSTAIN
    chunks = audio_chunks(out)
    assert len(chunks) == 1 and chunks[0][0] >= pipe.done_at  # nothing was voiced from the dropped G2 text
    assert [c["text"] for c in eleven.calls] == [ABSTAIN]


# ---- LLMClient.generate_stream_with_usage with a fake Responses API stream
def test_client_stream_yields_deltas_then_usage_and_logs_once(monkeypatch, tmp_path):
    from types import SimpleNamespace as NS

    from src.llm import LLMClient

    log = tmp_path / "usage.jsonl"
    monkeypatch.setenv("LLM_USAGE_LOG", str(log))
    done = NS(type="response.completed", response=NS(usage=NS(
        input_tokens=50, input_tokens_details=NS(cached_tokens=10), output_tokens=7,
        output_tokens_details=NS(reasoning_tokens=0))))
    sent = {}

    def create(**kw):
        sent.update(kw)
        return iter([NS(type="response.created"), NS(type="response.output_text.delta", delta="Hel"),
                     NS(type="response.output_text.delta", delta="lo."), done])

    client = LLMClient.__new__(LLMClient)
    client.default_model, client.client = "m", NS(responses=NS(create=create))
    out = list(client.generate_stream_with_usage("hi", meta={"call_type": "G2", "pipeline": "demo-E"}))
    assert out == ["Hel", "lo.", {"input_tokens": 50, "cached_tokens": 10, "output_tokens": 7, "reasoning_tokens": 0}]
    assert sent == {"model": "m", "input": "hi", "stream": True}  # nothing else differs from generate_with_usage
    assert len(log.read_text().splitlines()) == 1 and '"call_type": "G2"' in log.read_text()

    client.client = NS(responses=NS(create=lambda **kw: iter([NS(type="response.output_text.delta", delta="x")])))
    with pytest.raises(RuntimeError, match="before the response completed"):
        list(client.generate_stream_with_usage("hi"))
    assert len(log.read_text().splitlines()) == 1  # an unfinished stream is not logged


def test_late_g2_cost_is_added_to_the_conversation_total_when_it_completes(monkeypatch, tmp_path):
    out, _ = run_respond(monkeypatch, tmp_path, ScriptedPipe(g0_abstains=True, late_usd=0.002))
    first = next(u for _, u in out if isinstance(u[2], dict) and u[2].get("turns") == 1)  # the turn's own total
    assert first[2]["usd"] == 0 and first[2]["turns"] == 1 and "G2 (discarded, pending)" in first[7]
    last = out[-1][1]
    assert last[2]["usd"] == pytest.approx(0.002) and last[2]["in"] == 100 and last[2]["turns"] == 1
    assert "G2 (discarded) |" in last[7] and "pending" not in last[7]
