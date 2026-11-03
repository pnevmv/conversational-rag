"""LLM-as-a-judge for generated answers, with gpt-6-luna on the Azure Foundry endpoint.

The judge sees the dialogue (last turns), the user question, the reference answer, the gold
section and the context the model was given, and rates the model answer as correct / partial /
incorrect. Separately it says whether the answer is supported by the gold section or that context.
Abstentions are scored by rule, without a call: an abstention is correct on an unanswerable turn
and incorrect otherwise, and any real answer to an unanswerable turn is incorrect.

Settings in .env: AZURE_LUNA_ENDPOINT, AZURE_LUNA_KEY, AZURE_LUNA_DEPLOYMENT. JUDGE_ENDPOINT,
JUDGE_KEY and JUDGE_DEPLOYMENT override them (any deployment that serves the Responses API);
JUDGE_MODEL names the judge in output paths. Every call is written to the usage log of
src/llm/client.py with call type "judge".
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.evaluation.metrics import is_abstention
from src.llm.client import LLMClient

load_dotenv()

DEFAULT_MODEL = "gpt-6-luna"
HISTORY_TURNS = 4
MAX_SECTION_CHARS = 4000
MAX_CONTEXT_CHARS = 24000  # keeps the whole context (5 passages + 30 facts) for almost every question
SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}

JUDGE_PROMPT = """You are grading answers of a customer-service assistant for US government services \
(DMV, Social Security, Veterans Affairs, Federal Student Aid). The assistant must answer from the documents.

Conversation so far:
{history}

Customer question: {question}

Reference answer (written by a human agent from the document):
{reference}

Document section that contains the answer:
{section}

Context the assistant was given:
{context}

Assistant answer to grade:
{answer}

1. Verdict. Compare the assistant answer with the reference answer and the document section:
- "correct": it gives the key information of the reference answer. Wording and length may differ. \
Extra details do not lower the verdict as long as they are correct.
- "partial": it is on the right topic and gives part of the key information, but misses an important part, \
or it adds a detail that is wrong.
- "incorrect": it answers something else, misses the point, refuses although the information is available, \
or contradicts the document.
Sometimes the reference answer is a clarifying question (the human agent asks the customer something before \
answering, e.g. "Do you need help with health care?"). Then a relevant clarifying question, or relevant and \
correct information on the topic the agent asks about, is "correct"; a reply that is on topic but more general \
is "partial"; an off-topic reply is "incorrect".

2. Supported. Separately from the verdict, say whether everything the assistant states is backed by the \
document section or by the context it was given ("supported": true/false). The verdict must not depend on this.

Reply with JSON only, no other text:
{{"verdict": "correct" | "partial" | "incorrect", "supported": true | false, "reason": "<one short sentence>"}}"""


class JudgeClient(LLMClient):
    """Responses API client for the judge deployment (gpt-6-luna by default)."""

    def __init__(self, model: Optional[str] = None):
        endpoint = os.getenv("JUDGE_ENDPOINT") or os.getenv("AZURE_LUNA_ENDPOINT")
        key = os.getenv("JUDGE_KEY") or os.getenv("AZURE_LUNA_KEY")
        deployment = os.getenv("JUDGE_DEPLOYMENT") or os.getenv("AZURE_LUNA_DEPLOYMENT")
        missing = [n for n, v in (("AZURE_LUNA_ENDPOINT", endpoint), ("AZURE_LUNA_KEY", key),
                                  ("AZURE_LUNA_DEPLOYMENT", deployment)) if not v]
        if missing:
            raise ValueError(f"missing in .env: {', '.join(missing)}")
        super().__init__(api_key=key, base_url=endpoint, model=deployment)
        self.model = model or os.getenv("JUDGE_MODEL") or DEFAULT_MODEL


def format_history(history: List[Dict[str, str]], turns: int = HISTORY_TURNS) -> str:
    if not history:
        return "(this is the first turn)"
    return "\n".join(f"{'Customer' if t['role'] == 'user' else 'Agent'}: {t['utterance'].strip()}"
                     for t in history[-turns:])


NO_CONTEXT = "(none: the assistant answered without documents)"
UNKNOWN_CONTEXT = "(not stored for this system: judge \"supported\" against the document section only)"


def build_prompt(example: Dict[str, Any], answer: str, section_text: str, context: Optional[str] = None,
                 context_known: bool = True) -> str:
    context = context.strip() if context else ""
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + " [...]"
    return JUDGE_PROMPT.format(
        history=format_history(example.get("dialogue_history") or []),
        question=example["question"].strip(),
        reference=example["reference_answer"].strip(),
        section=(section_text or "(not available)")[:MAX_SECTION_CHARS],
        context=context or (NO_CONTEXT if context_known else UNKNOWN_CONTEXT),
        answer=answer.strip())


def parse_verdict(text: str) -> Optional[Dict[str, Any]]:
    """The first JSON object in the reply, if it has a valid verdict."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in SCORES:
        return None
    supported = data.get("supported")
    if isinstance(supported, str):
        supported = supported.strip().lower() == "true"
    return {"verdict": verdict, "supported": bool(supported) if supported is not None else None,
            "reason": str(data.get("reason", "")).strip()}


def rule_verdict(example: Dict[str, Any], answer: Optional[str]) -> Optional[Dict[str, Any]]:
    """Verdict for cases that need no judge call; None if the judge has to decide."""
    if not answer or not answer.strip():
        return {"verdict": "incorrect", "supported": None, "reason": "empty answer", "by": "rule"}
    abstained = is_abstention(answer)
    if example.get("is_unanswerable"):
        if abstained:
            return {"verdict": "correct", "supported": None, "reason": "abstained on an unanswerable turn", "by": "rule"}
        return {"verdict": "incorrect", "supported": None, "reason": "answered an unanswerable turn", "by": "rule"}
    if abstained:
        return {"verdict": "incorrect", "supported": None, "reason": "abstained on an answerable turn", "by": "rule"}
    return None
