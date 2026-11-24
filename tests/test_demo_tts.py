"""demo/tts.py without network: text cleaning, sentence splitting, streaming order, errors (no key needed)."""
import json
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))
import tts  # noqa: E402


class ApiError(Exception):
    def __init__(self, status_code, body):
        super().__init__(f"headers: {{'xi-api-key': 'secret-key'}}, status_code: {status_code}, body: {body}")
        self.status_code, self.body = status_code, body


class Resp:
    def __init__(self, data, cost):
        self.data, self.headers = iter([data[:3], data[3:]]), {"character-cost": cost}


class FakeClient:
    """Stands in for ElevenLabs(...): records the calls, audio is b"A:<text>"."""

    def __init__(self, delay=0.0, reject_context=False, fail_on=None):
        self.calls, self.delay, self.reject_context, self.fail_on = [], delay, reject_context, fail_on
        self.text_to_speech = self
        self.with_raw_response = self

    @contextmanager
    def convert(self, voice_id, **kw):
        self.calls.append({"voice_id": voice_id, "t": time.time(), **kw})
        if self.fail_on and self.fail_on in kw["text"]:
            raise ApiError(401, {"detail": {"status": "invalid_api_key", "message": "Invalid API key"}})
        if self.reject_context and ("previous_text" in kw or "next_text" in kw):
            raise ApiError(400, {"detail": {"message": "previous_text is not supported"}})
        time.sleep(self.delay)
        yield Resp(b"A:" + kw["text"].encode(), str(len(kw["text"])))


@pytest.fixture
def fake(monkeypatch, tmp_path):
    def make(**kw):
        client = FakeClient(**kw)
        monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-key")
        monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
        monkeypatch.setattr(tts, "_client", client)
        monkeypatch.setattr(tts, "_no_context", set())
        return client
    return make


def test_speakable_strips_citations_markdown_urls():
    assert tts.speakable("You **can** apply [2, F7] online at https://va.gov now [F3].") == \
        "You can apply online at now."


def test_speakable_keeps_meaningful_symbols():
    assert tts.speakable("Income > $1,000 for form my_file #5 is **ok**.") == "Income > $1,000 for form my_file #5 is ok."
    assert tts.speakable("## Steps\n> Use `Form A` and _then_ *wait*.") == "Steps Use Form A and then wait."


def test_sentences_split_and_abbreviations():
    text = ("Veterans in the U.S. can apply online. You need Form 21-526EZ, e.g. for a claim. "
            "Dr. Smith signs the form quickly! Is the fee $1,000.00 or 1.5 times more? No. 5 is the right office.")
    assert tts.sentences(text) == [
        "Veterans in the U.S. can apply online.",
        "You need Form 21-526EZ, e.g. for a claim.",
        "Dr. Smith signs the form quickly!",
        "Is the fee $1,000.00 or 1.5 times more?",
        "No. 5 is the right office.",
    ]


def test_sentences_merge_short_fragments():
    assert tts.sentences("Yes. You can apply for benefits online today. Ok.") == [
        "Yes. You can apply for benefits online today. Ok."]
    assert tts.sentences("Yes.") == ["Yes."]


def test_sentences_cut_long_sentence_at_comma_or_semicolon():
    long = "; ".join(f"you must send document number {i} to the regional office" for i in range(12)) + "."
    parts = tts.sentences(long)
    assert len(parts) > 1 and all(len(p) <= tts.MAX_SENTENCE for p in parts)
    assert " ".join(parts) == long and all(p.endswith(";") for p in parts[:-1])
    assert max(map(len, tts.sentences("word " * 300))) <= tts.MAX_SENTENCE  # no punctuation at all


def test_sentences_drop_markup_and_cap_length():
    assert tts.sentences("See **this** [2] now. Then go.") == ["See this now. Then go."]
    assert sum(map(len, tts.sentences("Hello there friend. " * 400))) <= tts.MAX_CHARS
    assert tts.sentences("[1] ") == []


ANSWER = "First you apply online at the portal. Then you wait for the letter. Finally you accept the offer."


def test_stream_order_prefetch_and_files(fake, tmp_path):
    client = fake(delay=0.2)
    st = {}
    t = time.time()
    got = []
    for chunk in tts.stream_answer(ANSWER, model="eleven_flash_v2_5", stats=st, out_dir=tmp_path / "tts"):
        got.append(chunk)
        time.sleep(0.2)  # the player is busy with this chunk while the next one is synthesized
    assert [c.decode() for c in got] == [f"A:{s}" for s in tts.sentences(ANSWER)]
    assert time.time() - t < 3 * 0.2 + 3 * 0.2 + 0.15  # 3 requests + 3 plays would be 1.2 s without overlap
    c = client.calls
    assert c[0]["voice_id"] == tts.DEFAULT_VOICE_ID and c[0]["model_id"] == "eleven_flash_v2_5"
    assert "previous_text" not in c[0] and c[0]["next_text"] == c[1]["text"]
    assert c[1]["previous_text"] == c[0]["text"] and c[1]["next_text"] == c[2]["text"]
    assert c[2]["previous_text"] == c[1]["text"] and "next_text" not in c[2]
    assert st["sentences"] == 3 and st["credits"] == st["chars"] and 0.2 <= st["first_audio"] < st["seconds"]
    assert Path(st["path"]).read_bytes() == b"".join(got)
    row = json.loads((tmp_path / "tts_usage.jsonl").read_text())
    assert row["sentences"] == 3 and row["model"] == "eleven_flash_v2_5" and "secret-key" not in json.dumps(row)


def test_stream_prefetches_next_sentence(fake, tmp_path):
    client = fake()
    gen = tts.stream_answer(ANSWER, out_dir=tmp_path)
    next(gen)
    deadline = time.time() + 2
    while len(client.calls) < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert len(client.calls) >= 2  # sentence 2 requested while sentence 1 is being consumed
    gen.close()


def test_stream_context_fallback(fake, tmp_path):
    client = fake(reject_context=True)
    got = list(tts.stream_answer(ANSWER, model="eleven_v3", out_dir=tmp_path))
    assert len(got) == 3
    rejected = [c for c in client.calls if "next_text" in c or "previous_text" in c]
    assert len(rejected) == 1  # tried once with context, then the model is remembered
    assert all("previous_text" not in c and "next_text" not in c for c in client.calls[1:])


def test_error_mapping_has_no_key(fake, tmp_path):
    fake(fail_on="Then you wait")
    st = {}
    got = []
    with pytest.raises(tts.TTSError) as e:
        for chunk in tts.stream_answer(ANSWER, stats=st, out_dir=tmp_path / "tts"):
            got.append(chunk)
    assert len(got) == 1  # the first sentence was already played
    assert "401" in str(e.value) and "Invalid API key" in str(e.value) and "secret-key" not in str(e.value)
    assert st["path"] and "secret-key" not in (tmp_path / "tts_usage.jsonl").read_text()


def test_network_error_has_no_key(fake, tmp_path, monkeypatch):
    class Boom(Exception):
        pass
    client = fake()
    monkeypatch.setattr(client, "convert", lambda *a, **k: (_ for _ in ()).throw(Boom("secret-key unreachable")))
    with pytest.raises(tts.TTSError, match="not reachable: Boom") as e:
        list(tts.stream_answer(ANSWER, out_dir=tmp_path))
    assert "secret-key" not in str(e.value)


def test_empty_answer_and_missing_key(fake, monkeypatch, tmp_path):
    fake()
    with pytest.raises(tts.TTSError, match="nothing to read"):
        list(tts.stream_answer("  [1] [F2, 3] ", out_dir=tmp_path))
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    assert not tts.enabled()
    with pytest.raises(tts.TTSError, match="not set"):
        list(tts.stream_answer("Hello there."))
