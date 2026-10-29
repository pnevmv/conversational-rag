"""A2: a tool-calling agent in a plain Python loop. It starts from the context of E and may look further with
at most MAX_TOOLS calls of search_passages / get_entity_facts, then must answer or refuse."""
import json
from typing import Any, Dict, List, Optional

from src.agents.world import NEW_FACTS, Turn, World
from src.llm import LLMCache, LLMClient
from src.llm.client import log_usage

MAX_TOOLS = 3
ABSTAIN = "Unfortunately, no relevant information is found."

SEARCH = {"type": "function", "name": "search_passages",
          "description": "Search the document sections of the government services with a new, self-contained query "
                         "and get the best 5 sections that are not in the context yet.",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}
FACTS = {"type": "function", "name": "get_entity_facts",
         "description": "Get facts from the knowledge graph about one entity (a service, document, fee, ...) "
                        "that are not in the context yet.",
         "parameters": {"type": "object", "properties": {"entity": {"type": "string"}}, "required": ["entity"]}}
ANSWER = {"type": "function", "name": "answer",
          "description": "Give the final reply to the customer. citations: the numbers of the passages and facts "
                         "used, for example [\"2\", \"F7\"].",
          "parameters": {"type": "object", "properties": {"text": {"type": "string"},
                                                          "citations": {"type": "array", "items": {"type": "string"}}},
                         "required": ["text", "citations"]}}
REFUSE = {"type": "function", "name": "refuse",
          "description": "Refuse to answer because the information is not available in the context or after looking "
                         "further.", "parameters": {"type": "object", "properties": {}}}

AGENT_NOTE = ("Before answering you may look further: call search_passages(query) or get_entity_facts(entity) "
              "when the context does not contain what you need, at most %d calls in total. Then finish by calling "
              "answer(text, citations) with your reply (the numbers of the passages and facts used go in "
              "citations, not in the text) or refuse() if the information is not available.") % MAX_TOOLS


def tool_prompt(head: str) -> str:
    anchor = "If the context does not contain the answer"
    assert anchor in head
    return head.replace(anchor, AGENT_NOTE + "\n" + anchor, 1)


def _call(client: LLMClient, cache: LLMCache, items, tools, meta) -> Dict[str, Any]:
    key = json.dumps({"i": items, "t": [t["name"] for t in tools]}, sort_keys=True, ensure_ascii=False)
    entry = cache.get_entry(key)
    if entry is not None:
        log_usage(client.default_model, entry.get("usage") or {}, meta, cache_hit=True)
        return json.loads(entry["response"])
    resp, usage = client.generate_with_tools(items, tools, tool_choice="required", meta=meta)
    cache.put(key, json.dumps(resp, ensure_ascii=False), usage)
    return resp


def run_a2(world: World, client: LLMClient, cache: LLMCache, t: Turn, prompt: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """prompt: the G2 prompt of E (citation request included) with the tool note; returns the trace and the answer."""
    sections, facts = list(t.sections), list(t.facts)
    items: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]
    n_tools, trace, final = 0, [], None
    for _ in range(MAX_TOOLS + 1):
        tools = [ANSWER, REFUSE] if n_tools >= MAX_TOOLS else [SEARCH, FACTS, ANSWER, REFUSE]
        resp = _call(client, cache, items, tools, meta)
        items += resp["output"]
        calls = [o for o in resp["output"] if o.get("type") == "function_call"]
        if not calls:
            final = {"kind": "answer", "text": resp["text"], "citations": []}
            break
        c = calls[0]
        try:
            args = json.loads(c.get("arguments") or "{}")
        except ValueError:
            args = None
        name = c["name"]
        if name == "refuse":
            final = {"kind": "refuse"}
            break
        if name == "answer" and isinstance(args, dict) and isinstance(args.get("text"), str):
            final = {"kind": "answer", "text": args["text"], "citations": [str(x) for x in args.get("citations") or []]}
            break
        n_tools += 1
        if name == "search_passages" and isinstance(args, dict) and args.get("query"):
            ranked = world.search([args["query"]])[0]
            cur = Turn(t.example, t.query, t.emb, t.gold, t.linked, sections, facts)
            new = world.add_sections(cur, ranked)
            sections += new
            out = world.render(new, []) if new else "No new sections."
            trace.append({"tool": name, "arg": args["query"], "new_sections": [s["section_id"] for s in new]})
        elif name == "get_entity_facts" and isinstance(args, dict) and args.get("entity"):
            linked = world.linker.link(args["entity"], k=1, skip_hubs=False)
            cur = Turn(t.example, t.query, t.emb, t.gold, t.linked, sections, facts)
            new = world.add_facts(cur, linked, t.emb) if linked else []
            facts += new
            out = world.render([], new, cite=True).replace("\n\nFacts:\n", "", 1) if new else "No new facts."
            trace.append({"tool": name, "arg": args["entity"], "entity": linked[0]["name"] if linked else None,
                          "new_facts": len(new)})
        else:
            out = "Error: unknown tool or invalid arguments."
            trace.append({"tool": name, "arg": None, "error": True})
        items.append({"type": "function_call_output", "call_id": c["call_id"], "output": out})
    if final is None:  # the loop ended without a terminal call (cannot happen with tool_choice=required)
        final = {"kind": "answer", "text": "", "citations": []}
    return {"trace": trace, "n_tools": n_tools, "final": final, "sections": sections, "facts": facts}
