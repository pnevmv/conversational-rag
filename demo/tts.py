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


def stream_answer(text: str, model: Optional[str] = None, voice_id: Optional[str] = None,
                  stats: Optional[Dict[str, Any]] = None, out_dir: Path = AUDIO_DIR) -> Iterator[bytes]:
    """Yield one mp3 chunk per sentence; the next sentence is synthesized while the current one is consumed.

    `stats` (optional dict) is filled while running: model, voice_id, sentences, chars, credits,
    first_audio (seconds from the first next() to the first chunk), seconds (to the last chunk), path (the
    whole answer as one mp3, written when the stream ends). The usage line is logged even if a request fails.
    """
    if not enabled():
        raise TTSError("ELEVENLABS_API_KEY is not set in .env")
    parts = sentences(text)
    if not parts:
        raise TTSError("nothing to read aloud")
    model = model or default_model()
    voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE_ID
    st = stats if stats is not None else {}
    st.update(model=model, voice_id=voice_id, sentences=len(parts), chars=sum(len(p) for p in parts),
              credits=None, first_audio=None, seconds=None, path=None)
    t0 = time.time()
    chunks: List[bytes] = []

    def job(i: int):
        return _convert(parts[i], model, voice_id, parts[i - 1] if i else "",
                        parts[i + 1] if i + 1 < len(parts) else "")

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        nxt = pool.submit(job, 0)
        for i in range(len(parts)):
            audio, credits = nxt.result()
            if i + 1 < len(parts):
                nxt = pool.submit(job, i + 1)  # runs while this chunk is played
            if credits is not None:
                st["credits"] = (st["credits"] or 0) + credits
            if st["first_audio"] is None:
                st["first_audio"] = time.time() - t0
            chunks.append(audio)
            st["seconds"] = time.time() - t0
            yield audio
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        if chunks:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.mp3"
            path.write_bytes(b"".join(chunks))
            st["path"] = str(path)
        _log({k: st[k] for k in ("model", "voice_id", "sentences", "chars", "credits", "first_audio", "seconds")},
             out_dir.parent / USAGE_LOG.name)
