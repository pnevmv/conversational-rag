from typing import Dict, List

from src.llm import LLMClient

REWRITE_PROMPT = (
    "You are a search query assistant. Given a conversation history and the "
    "current user message, rewrite the current message as a short, self-contained "
    "search query that can be understood without the conversation context.\n\n"
    "Rules:\n"
    "- Output ONLY the rewritten query, nothing else. No explanation, no quotes.\n"
    "- Resolve all pronouns and references (\"that\", \"it\", \"there\", \"those\") "
    "using the conversation history.\n"
    "- If the current message is already self-contained, return it unchanged.\n"
    "- Keep it concise — one sentence or a short phrase.\n\n"
    "Conversation history:\n"
    "{history}\n\n"
    "Current message: {question}\n\n"
    "Rewritten query:"
)

HISTORY_WINDOW = 6


def _format_history(history: List[Dict[str, str]]) -> str:
    lines = []
    for turn in history[-HISTORY_WINDOW:]:
        role = "User" if turn["role"] == "user" else "Agent"
        lines.append(f"{role}: {turn['utterance']}")
    return "\n".join(lines)


class QueryRewriter:
    """
    Rewrites a conversational user turn into a self-contained search query
    using the preceding dialogue history.

    For first-turn questions (no history) the question is returned unchanged.
    """

    def __init__(self, client: LLMClient = None):
        self._client = client or LLMClient()

    def rewrite(self, question: str, dialogue_history: List[Dict[str, str]], meta: Dict = None) -> str:
        if not dialogue_history:
            return question

        history_text = _format_history(dialogue_history)
        prompt = REWRITE_PROMPT.format(history=history_text, question=question)
        rewritten = self._client.generate(prompt=prompt, meta={**(meta or {}), "call_type": "rewrite"}).strip()
        return rewritten if rewritten else question
