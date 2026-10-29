"""The sufficiency check of the agent: is the retrieved context enough to answer?"""
import json
import re
from typing import Any, Dict

CHECK_PROMPT = (
    "You check whether retrieved context is enough to answer a customer's question about a government service.\n\n"
    "Question: {query}\n\n"
    "Context:\n{context}\n\n"
    "Decide whether the context states the information needed to answer the question. Passages that only treat a "
    "related topic do not count: answer sufficient only if the context contains the specific information asked for.\n\n"
    "Reply with one JSON object and nothing else:\n"
    '{{"sufficient": true or false, "missing": "<one sentence on what information is missing, empty if sufficient>", '
    '"search_query": "<a short self-contained search query for the missing information, empty if sufficient>"}}'
)


def check_prompt(query: str, context: str) -> str:
    return CHECK_PROMPT.format(query=query, context=context)


def parse_check(text: str) -> Dict[str, Any]:
    """{"ok", "sufficient", "missing", "search_query"}; a reply that cannot be parsed counts as sufficient."""
    bad = {"ok": False, "sufficient": True, "missing": "", "search_query": ""}
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if not m:
        return bad
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return bad
    if not isinstance(d.get("sufficient"), bool):
        return bad
    out = {"ok": True, "sufficient": d["sufficient"], "missing": str(d.get("missing") or "").strip(),
           "search_query": str(d.get("search_query") or "").strip()}
    if not out["sufficient"] and not out["search_query"]:
        return {**bad, "sufficient": False}  # insufficient without a query: parsed, but no round is possible
    return out
