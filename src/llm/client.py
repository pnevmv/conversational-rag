import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# Load environment variables from .env file
load_dotenv()

DEFAULT_BASE_URL = "https://2026-foundry.services.ai.azure.com/openai/v1"
DEFAULT_MODEL = "gpt-5.4-nano-smirnov"

# Every API call appends one JSON line with its token usage. LLM_USAGE_LOG overrides the path;
# "off" disables the log.
DEFAULT_USAGE_LOG = Path(__file__).resolve().parents[2] / "experiments" / "logs" / "llm_usage.jsonl"
_USAGE_LOCK = threading.Lock()


def usage_of(response: Any) -> Dict[str, Optional[int]]:
    """Input, cached input, output and reasoning tokens of a Responses API result."""
    u = getattr(response, "usage", None)
    return {
        "input_tokens": getattr(u, "input_tokens", None),
        "cached_tokens": getattr(getattr(u, "input_tokens_details", None), "cached_tokens", None),
        "output_tokens": getattr(u, "output_tokens", None),
        "reasoning_tokens": getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", None),
    }


def call_meta(example: Dict[str, Any], call_type: str, pipeline: Optional[str] = None) -> Dict[str, Any]:
    """Usage-log fields of one call for a dataset example."""
    return {"conversation_id": example.get("dialogue_id"), "turn_id": example.get("turn_id"),
            "example_id": example.get("example_id"), "call_type": call_type, "pipeline": pipeline}


def log_usage(model: str, usage: Dict[str, Optional[int]], meta: Optional[Dict[str, Any]] = None,
              cache_hit: bool = False) -> None:
    """Append one call to the usage log (conversation id, turn id and call type come from meta)."""
    target = os.getenv("LLM_USAGE_LOG", str(DEFAULT_USAGE_LOG))
    if target == "off":
        return
    meta = meta or {}
    row = {"t": time.time(), "model": model, "call_type": meta.get("call_type"),
           "conversation_id": meta.get("conversation_id"), "turn_id": meta.get("turn_id"),
           "example_id": meta.get("example_id"), "pipeline": meta.get("pipeline"),
           "cache_hit": cache_hit, **usage}
    path = Path(target)
    with _USAGE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


class LLMClient:
    """Reusable LLM client for sending prompts to Azure OpenAI / OpenAI compatible APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key not found. Please set AZURE_OPENAI_API_KEY in your .env file or environment."
            )

        self.base_url = (
            base_url
            or os.getenv("AZURE_OPENAI_BASE_URL")
            or DEFAULT_BASE_URL
        )
        self.default_model = (
            model
            or os.getenv("LLM_MODEL")
            or DEFAULT_MODEL
        )

        # A finite timeout so a dropped connection fails (and is retried) instead of hanging
        # for the SDK default of 10 minutes.
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=float(os.getenv("LLM_TIMEOUT", "120")),
        )

    def generate(self, prompt: str, model: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> str:
        """Send a prompt to the LLM and return the generated text response."""
        return self.generate_with_usage(prompt, model=model, meta=meta)[0]

    def generate_with_usage(self, prompt: str, model: Optional[str] = None,
                            meta: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Optional[int]]]:
        """Like generate(), but also return the token usage. Every call is written to the usage log."""
        target_model = model or self.default_model

        try:
            response = self.client.responses.create(
                model=target_model,
                input=prompt,
            )
        except OpenAIError as e:
            # Handle API errors without leaking credentials
            raise RuntimeError(f"LLM API request failed: {e}") from None
        usage = usage_of(response)
        log_usage(target_model, usage, meta)
        return response.output_text, usage


_default_client: Optional[LLMClient] = None


def get_default_client() -> LLMClient:
    """Get or create the singleton LLMClient instance."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def ask_llm(question: str, model: Optional[str] = None) -> str:
    """Convenience function matching the baseline interface."""
    client = get_default_client()
    return client.generate(prompt=question, model=model)
