"""Text to speech for the demo answers with ElevenLabs (optional experiment).

The answer is split into sentences and synthesized sentence by sentence with the official `elevenlabs`
SDK, so playback can start after the first sentence; the next sentence is requested while the current
one is handed to the player. Settings come from .env (loaded by python-dotenv, as for the LLM client):

    ELEVENLABS_API_KEY    required to enable the voice; never printed or logged
    ELEVENLABS_VOICE_ID   optional, default George (a premade voice available on every plan)
    ELEVENLABS_MODEL      optional, default eleven_flash_v2_5 (lowest latency)

The full answer is also saved as one mp3 in demo/logs/tts/ (ignored by git) and every answer appends a
line with its model, sentences, characters and times to demo/logs/tts_usage.jsonl.
"""
import json
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George, premade
DEFAULT_MODEL = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"
# Models offered in the demo. Flash and Turbo are the fast, cheaper ones; Multilingual v2 and v3
# sound more natural but are slower and cost more credits per character.
MODELS = ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2", "eleven_v3"]
MAX_CHARS = 2500  # a demo answer is far shorter; this only bounds the cost of a runaway answer
MIN_SENTENCE, MAX_SENTENCE = 20, 400  # characters per synthesized chunk
TIMEOUT = 60

DEMO_DIR = Path(__file__).resolve().parent
AUDIO_DIR = DEMO_DIR / "logs" / "tts"
USAGE_LOG = DEMO_DIR / "logs" / "tts_usage.jsonl"

# Words that end in a period without ending the sentence ("U.S. citizens", "Dr. Smith", "No. 5").
ABBREVIATIONS = {"e.g.", "i.e.", "dr.", "mr.", "mrs.", "ms.", "no.", "st.", "vs.", "jr.", "sr.", "inc.", "approx.",
                 "dept.", "est.", "fig.", "sec.", "vol."}

_client = None
_client_lock = threading.Lock()
_no_context = set()  # models that rejected previous_text / next_text


class TTSError(RuntimeError):
    """A failed synthesis; the message never contains the API key."""


def enabled() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY", "").strip())


def default_model() -> str:
    return os.getenv("ELEVENLABS_MODEL", "").strip() or DEFAULT_MODEL


def speakable(text: str) -> str:
    """Answer text as it should be read aloud: no markdown, citation brackets or URLs."""
    text = re.sub(r"\[(?:F?\d+)(?:\s*,\s*F?\d+)*\]", "", text)  # leftover [2] / [F7, 3]
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^[ \t]*(?:#{1,6}|>)[ \t]+", "", text, flags=re.M)  # heading / quote markers at line start
    text = re.sub(r"(\*{1,3}|\b_{1,2})(?=\S)(.+?)(?<=\S)\1", r"\2", text)  # **bold**, *em*, __b__, _em_
    text = text.replace("`", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text[:MAX_CHARS]


def _is_abbreviation(word: str) -> bool:
    w = word.lower().lstrip("(\"'“")
    return w in ABBREVIATIONS or bool(re.fullmatch(r"(?:[a-z]\.){1,}", w))  # U.S., J., a.m.


def _split_long(chunk: str) -> List[str]:
    """Cut a chunk above MAX_SENTENCE at the last ';' or ',' (else space) before the limit."""
    out = []
    while len(chunk) > MAX_SENTENCE:
        head = chunk[:MAX_SENTENCE]
        cut = max(head.rfind("; "), head.rfind(", "))
        if cut < MIN_SENTENCE:
            cut = head.rfind(" ")
        if cut < MIN_SENTENCE:
            cut = MAX_SENTENCE - 1
        out.append(chunk[:cut + 1].strip())
        chunk = chunk[cut + 1:].strip()
    return out + [chunk] if chunk else out


def sentences(text: str) -> List[str]:
    """Speakable text split into chunks for synthesis: sentences, short ones merged, long ones cut."""
    text = speakable(text)
    parts, start = [], 0
    # a boundary is . ! ? (and closing quote or bracket), a space, then a capital letter
    for m in re.finditer(r"[.!?][\"”’')\]]*\s+(?=[A-Z])", text):
        if m.group().strip()[0] == "." and _is_abbreviation(text[start:m.start() + 1].split()[-1]):
            continue
        parts.append(text[start:m.end()].strip())
        start = m.end()
    if text[start:].strip():
        parts.append(text[start:].strip())
    merged: List[str] = []
    for p in parts:
        if merged and (len(merged[-1]) < MIN_SENTENCE or len(p) < MIN_SENTENCE) \
                and len(merged[-1]) + 1 + len(p) <= MAX_SENTENCE:
            merged[-1] += " " + p
        else:
            merged.append(p)
    return [c for p in merged for c in _split_long(p)]


def complete_sentences(text: str, finished: bool) -> List[str]:
    """Chunks of a growing answer that will not change any more: all but the last one until it is finished."""
    parts = sentences(text)
    return parts if finished else parts[:-1]


def _get_client():
    """One ElevenLabs client per process, created on first use."""
    global _client
    with _client_lock:
        if _client is None:
            key = os.getenv("ELEVENLABS_API_KEY", "").strip()
            if not key:
                raise TTSError("ELEVENLABS_API_KEY is not set in .env")
            from elevenlabs.client import ElevenLabs
            _client = ElevenLabs(api_key=key, timeout=TIMEOUT)
        return _client


def _message(body: Any) -> str:
    d = body.get("detail", body) if isinstance(body, dict) else body
    msg = d.get("message", d) if isinstance(d, dict) else d
    return str(msg)[:300]


def _error(e: Exception) -> TTSError:
    """SDK exception as a TTSError with the status and the API's message, without the key."""
    status = getattr(e, "status_code", None)
    if status is not None:
        text = f"ElevenLabs HTTP {status}: {_message(getattr(e, 'body', None))}"
    else:
        text = f"ElevenLabs not reachable: {type(e).__name__}"
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    return TTSError(text.replace(key, "***") if key else text)


def _convert(text: str, model: str, voice_id: str, previous: str, following: str) -> Tuple[bytes, Optional[int]]:
    """One synthesis request; returns the mp3 bytes and the credits the API reports for it."""
    kw: Dict[str, Any] = {}
    if model not in _no_context:
        if previous:
            kw["previous_text"] = previous
        if following:
            kw["next_text"] = following
    client = _get_client()
    for attempt in (0, 1):
        try:
            with client.text_to_speech.with_raw_response.convert(
                    voice_id, text=text, model_id=model, output_format=OUTPUT_FORMAT, **kw) as resp:
                audio = b"".join(resp.data)
                cost = resp.headers.get("character-cost")
            break
        except Exception as e:
            if attempt == 0 and kw and getattr(e, "status_code", None) in (400, 422):
                _no_context.add(model)  # this model does not take neighbouring text: retry without it
                kw = {}
                continue
            raise _error(e) from None
    if not audio:
        raise TTSError("ElevenLabs returned no audio")
    return audio, int(cost) if cost and str(cost).isdigit() else None


def _log(row: Dict[str, Any], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), **row}) + "\n")


class VoiceStream:
    """Synthesizes sentences one request at a time, in order, while they are still being fed.

    feed() queues a sentence (its predecessor goes along as previous_text, and next_text when the caller
    knows it); ready() returns the chunks whose audio has arrived, in order; drain() waits for the rest.
    close() writes the whole answer as one mp3 and logs the usage line, even after an error.
    `start` is the time the first-audio time is measured from (default: creation).
    """

    def __init__(self, model: Optional[str] = None, voice_id: Optional[str] = None, start: Optional[float] = None,
                 out_dir: Path = AUDIO_DIR):
        if not enabled():
            raise TTSError("ELEVENLABS_API_KEY is not set in .env")
        self.model = model or default_model()
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE_ID
        self.start, self.out_dir = start or time.time(), out_dir
        self.stats: Dict[str, Any] = {"model": self.model, "voice_id": self.voice_id, "sentences": 0, "chars": 0,
                                      "credits": None, "first_audio": None, "seconds": None, "path": None}
        self._pool = ThreadPoolExecutor(max_workers=1)  # one request at a time keeps the order
        self._pending: List[Any] = []
        self._chunks: List[bytes] = []
        self._last = ""
        self._closed = False

    def feed(self, sentence: str, following: str = "") -> None:
        previous, self._last = self._last, sentence
        self.stats["sentences"] += 1
        self.stats["chars"] += len(sentence)
        self._pending.append(self._pool.submit(_convert, sentence, self.model, self.voice_id, previous, following))

    def _take(self) -> bytes:
        audio, credits = self._pending.pop(0).result()
        if credits is not None:
            self.stats["credits"] = (self.stats["credits"] or 0) + credits
        now = time.time() - self.start
        if self.stats["first_audio"] is None:
            self.stats["first_audio"] = now
        self.stats["seconds"] = now
        self._chunks.append(audio)
        return audio

    def ready(self) -> List[bytes]:
        out = []
        while self._pending and self._pending[0].done():
            out.append(self._take())
        return out

    def drain(self) -> Iterator[bytes]:
        while self._pending:
            yield self._take()

    def close(self) -> Dict[str, Any]:
        if not self._closed:
            self._closed = True
            self._pool.shutdown(wait=False, cancel_futures=True)
            if self._chunks:
                self.out_dir.mkdir(parents=True, exist_ok=True)
                path = self.out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.mp3"
                path.write_bytes(b"".join(self._chunks))
                self.stats["path"] = str(path)
            if self.stats["sentences"]:
                _log({k: self.stats[k] for k in ("model", "voice_id", "sentences", "chars", "credits",
                                                 "first_audio", "seconds")}, self.out_dir.parent / USAGE_LOG.name)
        return self.stats


def stream_answer(text: str, model: Optional[str] = None, voice_id: Optional[str] = None,
                  stats: Optional[Dict[str, Any]] = None, out_dir: Path = AUDIO_DIR) -> Iterator[bytes]:
    """Yield one mp3 chunk per sentence of a finished answer; the next sentences are synthesized meanwhile.

    `stats` (optional dict) is filled as described for VoiceStream (the saved mp3 is stats["path"]).
    """
    parts = sentences(text)
    if not parts:
        raise TTSError("nothing to read aloud")
    voice = VoiceStream(model, voice_id, out_dir=out_dir)
    try:
        for i, part in enumerate(parts):
            voice.feed(part, parts[i + 1] if i + 1 < len(parts) else "")
        yield from voice.drain()
    finally:
        result = voice.close()
        if stats is not None:
            stats.update(result)
