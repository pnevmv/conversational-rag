"""demo/pipeline.py generate(): G0 and G2 run together, the decision is the sequential one (fake client, no network)."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))
from pipeline import ABSTAIN, Pipeline  # noqa: E402


class FakeLLM:
    def __init__(self, outputs, delay=0.0):
        self.outputs, self.delay, self.calls, self.lock = outputs, delay, [], threading.Lock()

    def generate_with_usage(self, prompt, model=None, meta=None):
        with self.lock:
            self.calls.append(meta["call_type"])
        time.sleep(self.delay)
        return self.outputs[meta["call_type"]], {"input_tokens": 100, "cached_tokens": 0, "output_tokens": 10,
                                                 "reasoning_tokens": 0}


def run(outputs, p, delay=0.0):
    pipe = Pipeline.__new__(Pipeline)
    pipe.client = FakeLLM(outputs, delay)
    calls, times = [], {}
    raw = pipe.generate(p, "E", calls, times)
    return raw, calls, times, pipe.client


def test_abstaining_g0_gives_abstain_and_counts_discarded_g2():
    raw, calls, times, client = run({"G0": ABSTAIN, "G2": "You can apply online."}, {"G0": "a", "G2": "b"})
    assert raw == ABSTAIN
    assert [c["call"] for c in calls] == ["G0", "G2 (discarded)"] and sorted(client.calls) == ["G0", "G2"]
    assert all(c["input_tokens"] == 100 for c in calls) and "G0+G2" in times


def test_answering_g0_gives_g2_text():
    raw, calls, times, _ = run({"G0": "Yes, you can.", "G2": "You can apply online [2]."}, {"G0": "a", "G2": "b"})
    assert raw == "You can apply online [2]." and [c["call"] for c in calls] == ["G0", "G2"]


def test_same_prompt_is_one_call():
    raw, calls, times, client = run({"G0": "Yes, you can.", "G2": "never used"}, {"G0": "a", "G2": "a"})
    assert raw == "Yes, you can." and client.calls == ["G0"] and [c["call"] for c in calls] == ["G0"] and "G0" in times
    raw, calls, _, client = run({"G0": ABSTAIN, "G2": "x"}, {"G0": "a", "G2": "a"})
    assert raw == ABSTAIN and client.calls == ["G0"]


def test_calls_overlap():
    _, _, times, _ = run({"G0": "Yes.", "G2": "Yes, online."}, {"G0": "a", "G2": "b"}, delay=0.3)
    assert times["G0+G2"] < 0.5  # two calls of 0.3 s one after the other would take 0.6 s


def test_failed_g2_does_not_fail_an_abstaining_turn():
    pipe = Pipeline.__new__(Pipeline)

    class Flaky(FakeLLM):
        def generate_with_usage(self, prompt, model=None, meta=None):
            if meta["call_type"] == "G2":
                raise RuntimeError("LLM API request failed")
            return super().generate_with_usage(prompt, model, meta)

    pipe.client = Flaky({"G0": ABSTAIN})
    calls = []
    assert pipe.generate({"G0": "a", "G2": "b"}, "E", calls, {}) == ABSTAIN and [c["call"] for c in calls] == ["G0"]
