"""Thread-pool batch generation with retry/backoff and optional disk caching."""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from src.llm.cache import LLMCache
from src.llm.client import LLMClient, log_usage

# Error strings that indicate a retriable rate-limit or transient failure (including timeouts
# and dropped connections).
_RATE_LIMIT_SIGNALS = ("rate", "429", "too many", "throttl", "quota", "timed out", "timeout",
                       "connection", "502", "503", "504", "temporarily")


def _is_retriable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _RATE_LIMIT_SIGNALS)


def _call_once(
    client: LLMClient,
    prompt: str,
    cache: Optional[LLMCache],
    max_retries: int,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], str]:
    """Return (answer, status) for a single prompt. Checks cache first.

    A cache hit is logged with the usage stored when the call was made (empty for entries cached
    before usage was recorded) and cache_hit = true, so it is not counted as a new call.
    """
    if cache is not None:
        entry = cache.get_entry(prompt)
        if entry is not None:
            log_usage(client.default_model, entry.get("usage") or {}, meta, cache_hit=True)
            return entry["response"], "cached"

    for attempt in range(max_retries):
        try:
            answer, usage = client.generate_with_usage(prompt=prompt, meta=meta)
            if cache is not None:
                cache.put(prompt, answer, usage)
            return answer, "success"
        except Exception as exc:
            if _is_retriable(exc) and attempt < max_retries - 1:
                wait = min(2 ** attempt, 60)
                time.sleep(wait)
            else:
                return None, f"error: {exc}"

    return None, "failed"


def generate_batch(
    client: LLMClient,
    prompts: List[str],
    cache: Optional[LLMCache] = None,
    max_workers: int = 8,
    max_retries: int = 5,
    verbose: bool = True,
    metas: Optional[List[Dict[str, Any]]] = None,
) -> List[Tuple[Optional[str], str]]:
    """Generate answers for all prompts in parallel.

    Returns a list of (answer, status) in the same order as prompts.
    status is one of: "cached", "success", "error: ...", "failed".
    metas (optional, one per prompt): conversation_id, turn_id, call_type, ... for the usage log.
    """
    # Identical prompts are sent once: two concurrent calls with the same prompt would both
    # miss the cache and could get different answers from a non-deterministic model.
    unique = list(dict.fromkeys(prompts))
    if len(unique) < len(prompts):
        first_meta = {}
        for p, m in zip(prompts, metas or [None] * len(prompts)):
            first_meta.setdefault(p, m)
        answers = dict(zip(unique, _generate_unique(client, unique, cache, max_workers, max_retries, verbose,
                                                    [first_meta[p] for p in unique])))
        return [answers[p] for p in prompts]
    return _generate_unique(client, prompts, cache, max_workers, max_retries, verbose, metas)


def _generate_unique(client, prompts, cache, max_workers, max_retries, verbose, metas=None):
    n = len(prompts)
    results: List[Optional[Tuple]] = [None] * n
    done = [0]

    def _task(idx: int) -> Tuple[int, Optional[str], str]:
        answer, status = _call_once(client, prompts[idx], cache, max_retries, metas[idx] if metas else None)
        done[0] += 1
        if verbose and done[0] % max(1, n // 20) == 0:
            pct = done[0] / n * 100
            print(f"    {done[0]}/{n} ({pct:.0f}%) — last: {status}", flush=True)
        return idx, answer, status

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_task, i) for i in range(n)]
        for fut in as_completed(futures):
            idx, answer, status = fut.result()
            results[idx] = (answer, status)

    return results  # type: ignore[return-value]
