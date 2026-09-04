"""Disk cache for LLM responses, keyed by (experiment, example_id, prompt hash)."""
import hashlib
import json
from pathlib import Path
from typing import Optional


class LLMCache:
    """File-per-call cache stored under cache_dir.

    Key:  SHA-256 of the prompt text (deterministic, content-addressed).
    File: {cache_dir}/{hex_digest}.json
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def _path(self, prompt: str) -> Path:
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{h}.json"

    def get(self, prompt: str) -> Optional[str]:
        p = self._path(prompt)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                self._hits += 1
                return data["response"]
            except Exception:
                pass
        self._misses += 1
        return None

    def put(self, prompt: str, response: str) -> None:
        p = self._path(prompt)
        p.write_text(
            json.dumps({"response": response}, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total else 0.0,
        }
