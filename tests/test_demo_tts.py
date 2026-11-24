"""demo/tts.py without network: request shape, text cleaning, errors (no key is ever needed)."""
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))
import tts  # noqa: E402


class FakeResp(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(data)
        self.headers = headers or {}


def test_speakable_strips_citations_markdown_urls():
    assert tts.speakable("You **can** apply [2, F7] online at https://va.gov now [F3].") == \
        "You can apply online at now."


def test_synthesize_request_and_files(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    seen = {}

    def opener(req, timeout):
        seen["url"], seen["headers"], seen["body"] = req.full_url, dict(req.header_items()), json.loads(req.data)
        return FakeResp(b"ID3fake", {"character-cost": "21"})

    res = tts.synthesize("Hello [1], veteran.", model="eleven_flash_v2_5", out_dir=tmp_path / "tts", opener=opener)
    assert seen["url"].startswith(f"https://api.elevenlabs.io/v1/text-to-speech/{tts.DEFAULT_VOICE_ID}?")
    assert seen["headers"]["Xi-api-key"] == "test-key"
    assert seen["body"] == {"text": "Hello, veteran.", "model_id": "eleven_flash_v2_5"}
    assert Path(res["path"]).read_bytes() == b"ID3fake" and res["credits"] == 21
    row = json.loads((tmp_path / "tts_usage.jsonl").read_text())
    assert row["chars"] == len("Hello, veteran.") and "test-key" not in json.dumps(row)


def test_missing_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert not tts.enabled()
    with pytest.raises(tts.TTSError, match="not set"):
        tts.synthesize("hi")


def test_http_error_message_has_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-key")
    body = io.BytesIO(json.dumps({"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}).encode())

    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, body)

    with pytest.raises(tts.TTSError) as e:
        tts.synthesize("hi", out_dir=tmp_path, opener=opener)
    assert "401" in str(e.value) and "Invalid API key" in str(e.value) and "secret-key" not in str(e.value)
