"""The final system, one turn at a time, for the demo chat.

Every step calls the experiment code (nothing is reimplemented):
    rewrite   src.rag.query_rewriter (last 6 turns of the live history)
    passages  HybridRetriever (BM25 + bge-small, RRF) top 50 -> bge-reranker-base top 5
    facts     E: KGRetriever.rank_facts (30 one-hop facts); V1: the one-hop candidates scored by the
              same cross-encoder, top 10 (as experiments/step7_test.py)
    answer    gpt-5.4-nano, G2 + abstain(G0) (as experiments/graph_rag.generate), optionally with the
              citation prompt of experiments/sources.py

The graph is read from the JSON exports in experiments/kg_rag/ (made from Neo4j); Neo4j is not needed.
Nothing is written under experiments/: no LLM or reranker cache, and the usage log goes to demo/logs/.
"""
import os
import re
import queue
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("LLM_USAGE_LOG", str(PROJECT_ROOT / "demo" / "logs" / "usage.jsonl"))

import experiments.graph_rag as gr
import experiments.sources as src_attr
from experiments.generator_input import TAIL, build_prompt
from experiments.model_comparison import PRICES
from experiments.run_dev_subset import format_context
from src.evaluation.metrics import is_abstention
from src.kg_rag.queries import RETRIEVE_K, TOP_K
from src.llm import LLMClient
from src.rag.query_rewriter import REWRITE_PROMPT, _format_history

SYSTEMS = {"P": "P: passages", "E": "E: passages + 30 graph facts", "V1": "V1: passages + top 10 graph facts"}
V1_K = 10
PRICE = PRICES["gpt-5.4-nano"]
ABSTAIN = gr.ABSTAIN
# P has no facts, so its citation request does not mention them.
P_CITE_INSTRUCTION = ("After your answer, add in square brackets the numbers of the passages you used, "
                      "for example [2] or [2, 4]; passages are numbered [1] to [5].")


def display_title(title: str) -> str:
    """Document title without the corpus suffix ("GI Bill | Veterans Affairs#1" -> "GI Bill | Veterans Affairs")."""
    return re.sub(r"#\d+$", "", title).strip()


def cost_usd(usage: Dict[str, Optional[int]]) -> float:
    inp, cached, out = (usage.get("input_tokens") or 0), (usage.get("cached_tokens") or 0), (usage.get("output_tokens") or 0)
    return ((inp - cached) * PRICE["input"] + cached * PRICE["cached_input"] + out * PRICE["output"]) / 1e6


def late_call(fut: Future) -> Dict[str, Any]:
    """Record of a G2 call that is dropped (G0 abstained) while it may still be running.

    It reads "G2 (discarded, pending)" until the call completes; then its tokens and cost are filled in, the
    name becomes "G2 (discarded)" and `settled` is set. The call's usage-log line is written by the client.
    """
    rec: Dict[str, Any] = {"call": "G2 (discarded, pending)", "pending": True, "seconds": None, "usd": 0.0,
                           "input_tokens": None, "cached_tokens": None, "output_tokens": None, "reasoning_tokens": None,
                           "settled": threading.Event()}

    def settle(f: Future) -> None:
        try:
            rec.update(f.result()[1], call="G2 (discarded)")
        except Exception:  # not used anyway, so a failed call must not fail anything
            rec["call"] = "G2 (discarded, failed)"
        rec["usd"], rec["pending"] = cost_usd(rec), False
        rec["settled"].set()

    fut.add_done_callback(settle)  # runs at once if the call is already done
    return rec


def stream_view(raw: str, cite: bool = True) -> str:
    """Text of a growing answer as shown while it streams: citations removed, an unclosed "[" held back."""
    if cite:
        k = raw.rfind("[")
        if k >= 0 and "]" not in raw[k:]:
            raw = raw[:k]
    return src_attr.strip_citations(raw) if cite else raw


class Pipeline:
    def __init__(self, client: Optional[LLMClient] = None, log=print):
        from src.kg_rag.linker import EntityLinker
        from src.kg_rag.retrievers import KGRetriever
        from src.rag import HybridRetriever, Reranker

        t = time.time()
        log("loading the passage indexes (BM25, bge-small)")
        self.retriever = HybridRetriever()
        self.retriever.build_index()
        log("loading the cross-encoder")
        self.reranker = Reranker(cache_dir=None)
        log("loading the graph (JSON exports) and the entity linker")
        self.kg = KGRetriever(EntityLinker("full"))
        _ = self.kg.fact_emb
        gr._KG = self.kg  # graph_rag's fact helpers use the same graph
        self.template = gr.template()
        self.cite_template = src_attr.cite_template()
        self.cite_template_p = self.cite_template.replace(src_attr.CITE_INSTRUCTION, P_CITE_INSTRUCTION)
        self.client = client
        self.load_seconds = time.time() - t
        log(f"ready in {self.load_seconds:.0f} s")

    def llm(self) -> LLMClient:
        if self.client is None:
            self.client = LLMClient()
        return self.client

    # ------------------------------------------------------------------ steps
    def rewrite(self, question: str, history: List[Dict[str, str]], calls: List[Dict]) -> str:
        if not history:
            return question
        prompt = REWRITE_PROMPT.format(history=_format_history(history), question=question)
        text, usage = self.llm().generate_with_usage(prompt, meta={"call_type": "rewrite", "pipeline": "demo"})
        calls.append({"call": "rewrite", **usage})
        return text.strip() or question

    def passages(self, query: str) -> List[Dict[str, Any]]:
        """Step 4: hybrid top 50, cross-encoder top 5 (sections as in the E records)."""
        cands = self.retriever.retrieve(query, top_k=RETRIEVE_K)
        docs, _ = self.reranker.rerank_many([query], [cands], top_k=TOP_K)[0]
        from src.data.loader import make_section_id
        return [self.kg.section_result(make_section_id(d["doc_id"], d["id_sp"]), d["rank"], d["reranker_score"])
                for d in docs]

    def facts(self, query: str, system: str) -> Dict[str, Any]:
        emb = self.kg.linker.encode([query])[0]
        linked = self.kg.link(query, emb)
        if system == "E":
            return {"linked": linked, "facts": self.kg.rank_facts(linked, emb)}
        rel = sorted({i for l in linked for i in self.kg.adjacent[l["entity_id"]]})
        cands = [{"text": gr.fact_text(self.kg.relations[i]), "relation_index": i} for i in rel]
        docs, _ = self.reranker.rerank_many([query], [cands], top_k=V1_K)[0] if cands else ([], None)
        facts = [{"rank": k, "relation_index": d["relation_index"], "score": float(d["reranker_score"]),
                  **self.kg.relations[d["relation_index"]]} for k, d in enumerate(docs, start=1)]
        return {"linked": linked, "facts": facts}

    def context(self, system: str, ranking: List[Dict[str, Any]], facts: List[Dict[str, Any]]) -> str:
        ctx = format_context(ranking[:TOP_K])
        if system == "E":
            return ctx + "\n\nFacts:\n" + self.kg.format_facts(facts)
        if system == "V1":
            return ctx + ("\n\nFacts:\n" + gr.facts_block([f["relation_index"] for f in facts]) if facts else "")
        return ctx

    def prompts(self, system: str, context: str, question: str, history: List[Dict[str, str]],
                rewritten: str, cite: bool) -> Dict[str, str]:
        """G0 and G2 prompts exactly as graph_rag.generate (and sources.run_cite for citations)."""
        ex = {"question": question, "dialogue_history": history}
        head = self.template.format(context=context, question="\x00").split("\n\nCustomer: \x00")[0]
        out = {"G0": head + TAIL.format(question=question)}
        if cite:
            tmpl = self.cite_template_p if system == "P" else self.cite_template
            chead = tmpl.format(context=src_attr.cite_context(context), question="\x00").split("\n\nCustomer: \x00")[0]
            out["G2"] = build_prompt(chead, ex, rewritten, "G2", None)
        else:
            out["G2"] = build_prompt(head, ex, rewritten, "G2", None)
        return out

    # ------------------------------------------------------------------ one turn
    def prepare(self, question: str, history: List[Dict[str, str]], system: str, cite: bool) -> Dict[str, Any]:
        """Everything before the generator: rewrite, passages, facts, context and the G0 / G2 prompts."""
        calls: List[Dict] = []
        times: Dict[str, float] = {}

        t = time.time()
        rewritten = self.rewrite(question, history, calls)
        times["rewrite"] = time.time() - t

        t = time.time()
        ranking = self.passages(rewritten)
        times["passages"] = time.time() - t

        facts: List[Dict[str, Any]] = []
        if system in ("E", "V1"):
            t = time.time()
            facts = self.facts(rewritten, system)["facts"]
            times["facts"] = time.time() - t
        context = self.context(system, ranking, facts)
        p = self.prompts(system, context, question, history, rewritten, cite)
        return {"question": question, "system": system, "cite": cite, "rewritten": rewritten, "ranking": ranking[:TOP_K],
                "facts": facts, "context": context, "prompts": p, "calls": calls, "times": times}

    def finish(self, st: Dict[str, Any], raw: str) -> Dict[str, Any]:
        """The turn's result from the prepared state and the raw generator output."""
        final = src_attr.strip_citations(raw) if st["cite"] else raw
        sources = self.sources(raw, final, st["context"], st["ranking"], st["cite"])
        for c in st["calls"]:
            if "settled" not in c:  # a late call fills in its own cost
                c["usd"] = cost_usd(c)
        late = [c for c in st["calls"] if "settled" in c and not c["settled"].is_set()]  # not in usd or tokens yet
        return {**{k: st[k] for k in ("question", "rewritten", "system", "cite", "ranking", "facts", "context",
                                      "prompts", "calls", "times")},
                "raw_answer": raw, "answer": final, "abstained": is_abstention(final), "sources": sources,
                "late": late, "usd": sum(c["usd"] for c in st["calls"] if c not in late)}

    # ------------------------------------------------------------------ one turn
    def answer(self, question: str, history: List[Dict[str, str]], system: str = "E", cite: bool = True) -> Dict[str, Any]:
        st = self.prepare(question, history, system, cite)
        raw = self.generate(st["prompts"], system, st["calls"], st["times"])
        return self.finish(st, raw)

    def answer_stream(self, question: str, history: List[Dict[str, str]], system: str = "E", cite: bool = True):
        """Like answer(), but as events: ("prepared", state), ("delta", text) while G2 is written,
        ("g0", abstained) when G0 has decided, ("done", result).

        G0 runs in a thread (whole, it only decides on abstention) while G2 is streamed in this one. With
        G2 == G0 the single call is streamed and its decision comes with the last delta. The result is the
        one answer() gives for the same model outputs: ABSTAIN if G0 abstains (the streamed G2 is then
        "G2 (discarded)"), else the G2 text.
        """
        st = self.prepare(question, history, system, cite)
        yield "prepared", st
        p, calls, client = st["prompts"], st["calls"], self.llm()
        single = p["G2"] == p["G0"]
        kind = "G0" if single else "G2"
        events: "queue.Queue" = queue.Queue()
        fut: Future = Future()  # (text, call record) of the streamed call

        def pump() -> None:  # the streamed call runs on its own, so it can outlive a dropped answer
            t, parts, usage = time.time(), [], None
            try:
                for x in client.generate_stream_with_usage(p[kind], meta={"call_type": kind, "pipeline": f"demo-{system}"}):
                    if isinstance(x, str):
                        parts.append(x)
                        events.put(("delta", x))
                    else:
                        usage = x
                fut.set_result(("".join(parts), {"call": kind, "seconds": time.time() - t, **usage}))
            except Exception as e:
                fut.set_exception(e)
            events.put(("end", None))

        t = time.time()
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            f0 = None if single else pool.submit(self._call, client, "G0", p, system)
            if f0:
                f0.add_done_callback(lambda f: events.put(("g0", None)))
            threading.Thread(target=pump, daemon=True).start()
            abstained, ended = None, False
            while True:
                k, v = events.get()
                if k == "delta":
                    yield "delta", v
                elif k == "g0":
                    a0, c0 = f0.result()  # a failed G0 fails the turn
                    abstained = is_abstention(a0)
                    yield "g0", abstained
                    if abstained:
                        break
                else:
                    ended = True
                if ended and (single or abstained is not None):
                    break
        finally:
            pool.shutdown(wait=False)
        if single:
            text, c2 = fut.result()
            abstained = is_abstention(text)
            yield "g0", abstained
            calls.append(c2)
            raw = ABSTAIN if abstained else text
        elif abstained:  # G2 is not waited for; it finishes in the background
            calls += [c0, late_call(fut)]
            raw = ABSTAIN
        else:
            text, c2 = fut.result()
            calls += [c0, c2]
            raw = text
        st["times"]["G0" if single or abstained else "G0+G2"] = time.time() - t  # G2 is not waited for after an abstention
        yield "done", self.finish(st, raw)

    def _call(self, client: LLMClient, kind: str, p: Dict[str, str], system: str):
        t = time.time()
        text, usage = client.generate_with_usage(p[kind], meta={"call_type": kind, "pipeline": f"demo-{system}"})
        return text, {"call": kind, "seconds": time.time() - t, **usage}

    def generate(self, p: Dict[str, str], system: str, calls: List[Dict], times: Dict[str, float]) -> str:
        """G0 (abstention check) and G2 (answer), as graph_rag.generate, but started together.

        G2 does not depend on G0, so both calls run at once. The decision is unchanged: an abstaining G0
        gives ABSTAIN at once and the G2 text is dropped; its call is not waited for, but still costs and is
        listed as "G2 (discarded, pending)" until it completes (see late_call). Without an abstention the
        turn waits for G2. With G2 == G0 there is a single call.
        """
        client = self.llm()  # created here, before the threads start

        t = time.time()
        if p["G2"] == p["G0"]:
            a0, c0 = self._call(client, "G0", p, system)
            calls.append(c0)
            times["G0"] = time.time() - t
            return ABSTAIN if is_abstention(a0) else a0
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            f0, f2 = (pool.submit(self._call, client, k, p, system) for k in ("G0", "G2"))
            a0, c0 = f0.result()
            calls.append(c0)
            if is_abstention(a0):  # G2 is not waited for; it finishes in the background
                calls.append(late_call(f2))
                times["G0"] = time.time() - t
                return ABSTAIN
            raw, c2 = f2.result()
            calls.append(c2)
        finally:
            pool.shutdown(wait=False)
        times["G0+G2"] = time.time() - t
        return raw

    def sources(self, raw: str, final: str, context: str, ranking: List[Dict], cite: bool) -> List[Dict[str, str]]:
        """Cited sections (citation prompt) or the best post-hoc match (sources.py method A)."""
        if is_abstention(final):
            return []
        cands = src_attr.candidates({"context": context, "retrieved_sections": [r["section_id"] for r in ranking]})
        by_label = {lab: sid for lab, sid, _ in cands}
        if cite:
            labels = src_attr.parse_citations(raw)
            sids = [by_label[l] for l in labels if l in by_label]
            how = "cited"
        else:
            sids = src_attr.rank_sources(final, cands)[:1]
            labels, how = [], "best match"
        out, seen = [], set()
        for sid in sids:
            if sid not in self.kg.sections:
                continue
            s = self.kg.sections[sid]
            key = (display_title(s["title"]), s.get("section_title") or "")  # shown once even if several sections match
            if key in seen:
                continue
            seen.add(key)
            out.append({"section_id": sid, "title": display_title(s["title"]), "section": s.get("section_title") or "", "how": how})
        return out
