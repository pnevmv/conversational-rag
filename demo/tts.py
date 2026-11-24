"""Text to speech for the demo answers with ElevenLabs (optional experiment).

One REST call per answer (POST /v1/text-to-speech/{voice_id}), standard library only, so the demo
needs no extra package. Settings come from .env (loaded by python-dotenv, as for the LLM client):

    ELEVENLABS_API_KEY    required to enable the voice; never printed or logged
    ELEVENLABS_VOICE_ID   optional, default George (a premade voice available on every plan)
    ELEVENLABS_MODEL      optional, default eleven_flash_v2_5 (lowest latency)

The audio files go to demo/logs/tts/ (ignored by git) and each call appends a line with its
characters, model and time to demo/logs/tts_usage.jsonl.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={fmt}"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George, premade
DEFAULT_MODEL = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"
# Models offered in the demo. Flash and Turbo are the fast, cheaper ones; Multilingual v2 and v3
# sound more natural but are slower and cost more credits per character.
MODELS = ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2", "eleven_v3"]
MAX_CHARS = 2500  # a demo answer is far shorter; this only bounds the cost of a runaway answer
TIMEOUT = 60

DEMO_DIR = Path(__file__).resolve().parent
AUDIO_DIR = DEMO_DIR / "logs" / "tts"
USAGE_LOG = DEMO_DIR / "logs" / "tts_usage.jsonl"


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
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text[:MAX_CHARS]


def synthesize(text: str, model: Optional[str] = None, voice_id: Optional[str] = None,
               out_dir: Path = AUDIO_DIR, opener=urllib.request.urlopen) -> Dict[str, Any]:
    """Speak one answer; returns the mp3 path, the characters sent, the model and the seconds taken."""
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise TTSError("ELEVENLABS_API_KEY is not set in .env")
    text = speakable(text)
    if not text:
        raise TTSError("nothing to read aloud")
    model = model or default_model()
    voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE_ID
    req = urllib.request.Request(
        API_URL.format(voice_id=voice_id, fmt=OUTPUT_FORMAT),
        data=json.dumps({"text": text, "model_id": model}).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    t = time.time()
    try:
        with opener(req, timeout=TIMEOUT) as resp:
            audio = resp.read()
            char_cost = resp.headers.get("character-cost") if getattr(resp, "headers", None) else None
    except urllib.error.HTTPError as e:
        raise TTSError(f"ElevenLabs HTTP {e.code}: {_detail(e)}") from None
    except urllib.error.URLError as e:
        raise TTSError(f"ElevenLabs not reachable: {e.reason}") from None
    seconds = time.time() - t
    if not audio:
        raise TTSError("ElevenLabs returned no audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.mp3"
    path.write_bytes(audio)
    res = {"path": str(path), "chars": len(text), "model": model, "voice_id": voice_id, "seconds": seconds,
           "credits": int(char_cost) if char_cost and str(char_cost).isdigit() else None}
    _log(res, out_dir.parent / USAGE_LOG.name)
    return res


def _detail(e: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(e.read().decode("utf-8", "replace"))
        d = body.get("detail", body)
        return d.get("message", str(d)) if isinstance(d, dict) else str(d)
    except Exception:
        return e.reason or "error"


def _log(res: Dict[str, Any], log_path: Path = USAGE_LOG) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    row = {"t": time.time(), **{k: res[k] for k in ("model", "voice_id", "chars", "credits", "seconds")}}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
