import unittest
from unittest.mock import MagicMock

from src.rag.query_rewriter import QueryRewriter, _format_history, HISTORY_WINDOW


class TestFormatHistory(unittest.TestCase):

    def test_empty_history(self):
        self.assertEqual(_format_history([]), "")

    def test_single_user_turn(self):
        history = [{"role": "user", "utterance": "Hello"}]
        self.assertIn("User: Hello", _format_history(history))

    def test_agent_turn_label(self):
        history = [{"role": "agent", "utterance": "Hi there"}]
        self.assertIn("Agent: Hi there", _format_history(history))

    def test_alternating_roles(self):
        history = [
            {"role": "user", "utterance": "What are the fees?"},
            {"role": "agent", "utterance": "There is a $10 fee."},
        ]
        result = _format_history(history)
        self.assertIn("User: What are the fees?", result)
        self.assertIn("Agent: There is a $10 fee.", result)

    def test_window_truncation(self):
        history = [{"role": "user", "utterance": f"turn {i}"} for i in range(HISTORY_WINDOW + 4)]
        result = _format_history(history)
        lines = result.strip().splitlines()
        self.assertEqual(len(lines), HISTORY_WINDOW)

    def test_window_keeps_most_recent(self):
        history = [{"role": "user", "utterance": f"turn {i}"} for i in range(HISTORY_WINDOW + 2)]
        result = _format_history(history)
        self.assertIn(f"turn {HISTORY_WINDOW + 1}", result)
        self.assertNotIn("turn 0", result)


class TestQueryRewriter(unittest.TestCase):

    def _make_rewriter(self, response: str) -> QueryRewriter:
        client = MagicMock()
        client.generate.return_value = response
        return QueryRewriter(client=client)

    def test_no_history_returns_question_unchanged(self):
        rewriter = self._make_rewriter("should not be called")
        result = rewriter.rewrite("What are the fees?", [])
        self.assertEqual(result, "What are the fees?")

    def test_no_history_does_not_call_llm(self):
        client = MagicMock()
        rewriter = QueryRewriter(client=client)
        rewriter.rewrite("What are the fees?", [])
        client.generate.assert_not_called()

    def test_with_history_calls_llm(self):
        client = MagicMock()
        client.generate.return_value = "What are the DMV registration fees?"
        rewriter = QueryRewriter(client=client)
        history = [{"role": "user", "utterance": "I need to register my car."}]
        rewriter.rewrite("What are the fees?", history)
        client.generate.assert_called_once()

    def test_rewritten_query_returned(self):
        rewriter = self._make_rewriter("What are the DMV registration fees?")
        history = [{"role": "user", "utterance": "I need to register my car."}]
        result = rewriter.rewrite("What are the fees?", history)
        self.assertEqual(result, "What are the DMV registration fees?")

    def test_empty_llm_response_falls_back_to_question(self):
        rewriter = self._make_rewriter("   ")
        history = [{"role": "user", "utterance": "I need to register my car."}]
        result = rewriter.rewrite("What are the fees?", history)
        self.assertEqual(result, "What are the fees?")

    def test_history_and_question_appear_in_prompt(self):
        client = MagicMock()
        client.generate.return_value = "rewritten"
        rewriter = QueryRewriter(client=client)
        history = [{"role": "agent", "utterance": "Sure, I can help."}]
        rewriter.rewrite("Where is it located?", history)
        prompt = client.generate.call_args[1]["prompt"]
        self.assertIn("Sure, I can help.", prompt)
        self.assertIn("Where is it located?", prompt)


if __name__ == "__main__":
    unittest.main()
