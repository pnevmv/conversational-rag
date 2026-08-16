import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# Load environment variables from .env file
load_dotenv()

DEFAULT_BASE_URL = "https://2026-foundry.services.ai.azure.com/openai/v1"
DEFAULT_MODEL = "gpt-5.4-nano-smirnov"


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

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """Send a prompt to the LLM and return the generated text response."""
        target_model = model or self.default_model

        try:
            response = self.client.responses.create(
                model=target_model,
                input=prompt,
            )
            return response.output_text
        except OpenAIError as e:
            # Handle API errors without leaking credentials
            raise RuntimeError(f"LLM API request failed: {e}") from None


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
