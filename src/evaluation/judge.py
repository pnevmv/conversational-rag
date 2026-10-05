"""LLM-as-a-judge for generated answers, through the Hugging Face inference router.

The judge sees the dialogue (last turns), the user question, the reference answer and the
gold section, and rates the model answer as correct / partial / incorrect, plus whether the
answer is supported by the gold section. Abstentions are scored by rule, without a call:
an abstention is correct on an unanswerable turn and incorrect otherwise, and any real
answer to an unanswerable turn is incorrect.

Settings in .env: HF_TOKEN, optionally JUDGE_MODEL and JUDGE_BASE_URL (any OpenAI-compatible
server, e.g. a local Ollama at http://localhost:11434/v1).
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from src.evaluation.metrics import is_abstention

load_dotenv()

DEFAULT_BASE_URL = "https://router.huggingface.co/v1"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
HISTORY_TURNS = 4
MAX_SECTION_CHARS = 4000
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

Assistant answer to grade:
{answer}

Grade the assistant answer:
- "correct": it gives the information of the reference answer (wording and length may differ) and says nothing that contradicts the document.
- "partial": it is on the right topic and contains part of the needed information, but misses an important part or adds a wrong detail.
- "incorrect": it answers something else, misses the point, refuses although the information is available, or contradicts the document.
Also say whether everything the assistant states is supported by the document section ("supported": true/false).

Reply with JSON only, no other text:
{{"verdict": "correct" | "partial" | "incorrect", "supported": true | false, "reason": "<one short sentence>"}}"""


class JudgeClient:
    """Chat-completions client for the judge (OpenAI-compatible Hugging Face router)."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        base_url = base_url or os.getenv("JUDGE_BASE_URL") or DEFAULT_BASE_URL
        # A local server (e.g. Ollama) accepts any key; the Hugging Face router needs HF_TOKEN.
        api_key = api_key or os.getenv("JUDGE_API_KEY") or os.getenv("HF_TOKEN")
        if not api_key:
            if base_url == DEFAULT_BASE_URL:
                raise ValueError("HF_TOKEN not set. Add your Hugging Face token to .env.")
            api_key = "none"
        self.model = model or os.getenv("JUDGE_MODEL") or DEFAULT_MODEL
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=float(os.getenv("LLM_TIMEOUT", "120")))

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}],
                temperature=0, max_tokens=200)
            return response.choices[0].message.content or ""
        except OpenAIError as e:
            raise RuntimeError(f"Judge request failed: {e}") from None


def format_history(history: List[Dict[str, str]], turns: int = HISTORY_TURNS) -> str:
    if not history:
        return "(this is the first turn)"
    return "\n".join(f"{'Customer' if t['role'] == 'user' else 'Agent'}: {t['utterance'].strip()}"
                     for t in history[-turns:])


def build_prompt(example: Dict[str, Any], answer: str, section_text: str) -> str:
    return JUDGE_PROMPT.format(
        history=format_history(example.get("dialogue_history") or []),
        question=example["question"].strip(),
        reference=example["reference_answer"].strip(),
        section=(section_text or "(not available)")[:MAX_SECTION_CHARS],
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
