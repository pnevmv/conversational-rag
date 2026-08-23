import re
import string
from collections import Counter
from typing import Dict


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, remove articles, collapse whitespace."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def exact_match(prediction: str, reference: str) -> int:
    """Return 1 if normalized prediction equals normalized reference, else 0."""
    return int(_normalize(prediction) == _normalize(reference))


def token_f1(prediction: str, reference: str) -> float:
    """Compute token-level F1 between prediction and reference after normalization."""
    pred_tokens = _normalize(prediction).split()
    ref_tokens = _normalize(reference).split()

    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0

    common = Counter(pred_tokens) & Counter(ref_tokens)
    num_common = sum(common.values())

    if num_common == 0:
        return 0.0

    precision = num_common / len(pred_tokens)
    recall = num_common / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def compute_metrics(prediction: str, reference: str) -> Dict[str, float]:
    """Return EM and token-level F1 for a single prediction/reference pair."""
    return {
        "exact_match": float(exact_match(prediction, reference)),
        "f1": token_f1(prediction, reference),
    }
