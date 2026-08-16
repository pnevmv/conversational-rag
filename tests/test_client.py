import os
import unittest
from unittest.mock import patch

from src.llm.client import LLMClient


class TestLLMClient(unittest.TestCase):
    """Unit tests for the reusable LLM client."""

    @patch.dict(os.environ, {}, clear=True)
    def test_client_missing_key_raises_error(self):
        """Test that LLMClient raises ValueError when no API key is available."""
        with self.assertRaises(ValueError) as context:
            LLMClient(api_key=None)
        self.assertIn("API key not found", str(context.exception))

    def test_client_custom_config(self):
        """Test client initialization with explicit configuration."""
        client = LLMClient(
            api_key="fake-key-for-test",
            base_url="https://custom.endpoint.com/v1",
            model="custom-model",
        )
        self.assertEqual(client.api_key, "fake-key-for-test")
        self.assertEqual(client.base_url, "https://custom.endpoint.com/v1")
        self.assertEqual(client.default_model, "custom-model")


if __name__ == "__main__":
    unittest.main()
