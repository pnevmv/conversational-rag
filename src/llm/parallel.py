"""Thread-pool batch generation with retry/backoff and optional disk caching."""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from src.llm.cache import LLMCache
from src.llm.client import LLMClient

# Error strings that indicate a retriable rate-limit or transient failure.
_RATE_LIMIT_SIGNALS = ("rate", "429", "too many", "throttl", "quota")


def _is_retriable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _RATE_LIMIT_SIGNALS)


def _call_once(
    client: LLMClient,
    prompt: str,
    cache: Optional[LLMCache],
    max_retries: int,
) -> Tuple[Optional[str], str]:
    """Return (answer, status) for a single prompt. Checks cache first."""
    if cache is not None:
        cached = cache.get(prompt)
        if cached is not None:
            return cached, "cached"

    for attempt in range(max_retries):
        try:
            answer = client.generate(prompt=prompt)
            if cache is not None:
                cache.put(prompt, answer)
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
) -> List[Tuple[Optional[str], str]]:
    """Generate answers for all prompts in parallel.

    Returns a list of (answer, status) in the same order as prompts.
    status is one of: "cached", "success", "error: ...", "failed".
    """
    n = len(prompts)
    results: List[Optional[Tuple]] = [None] * n
    done = [0]

    def _task(idx: int) -> Tuple[int, Optional[str], str]:
        answer, status = _call_once(client, prompts[idx], cache, max_retries)
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
