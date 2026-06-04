"""FinBERT sentiment scorer (ProsusAI/finbert) with VADER fallback.

FinBERT is a BERT model fine-tuned on financial news. It returns class
probabilities over {positive, negative, neutral}; we convert to a compound
score in [-1, 1] as `p_pos - p_neg`, matching VADER's semantic so callers
don't need to care which backend they got.

The model (~440MB) downloads to `~/.cache/huggingface` on first use. If the
model fails to load (offline, disk full, etc.) we silently fall back to VADER
— a degraded but functional path.
"""

from __future__ import annotations

import logging
import threading
import warnings
from typing import Iterable

warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="huggingface_hub")

logger = logging.getLogger(__name__)

MODEL_NAME = "ProsusAI/finbert"
BATCH_SIZE = 32
MAX_LEN = 128

_lock = threading.Lock()
_state: dict = {"loaded": False, "tokenizer": None, "model": None,
                "pos_idx": None, "neg_idx": None, "backend": None}


def _load() -> bool:
    """Load FinBERT lazily. Returns True on success, False if we fell back."""
    if _state["loaded"]:
        return _state["backend"] == "finbert"

    with _lock:
        if _state["loaded"]:
            return _state["backend"] == "finbert"
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
            model.eval()

            # Resolve label indices defensively — ProsusAI/finbert's label order
            # is documented as {0:positive, 1:negative, 2:neutral}, but defer to
            # the model config so we don't break if it ever changes.
            id2label = {int(k): v.lower() for k, v in model.config.id2label.items()}
            pos_idx = next(i for i, lab in id2label.items() if lab.startswith("pos"))
            neg_idx = next(i for i, lab in id2label.items() if lab.startswith("neg"))

            _state.update({
                "loaded": True, "backend": "finbert",
                "tokenizer": tokenizer, "model": model, "torch": torch,
                "pos_idx": pos_idx, "neg_idx": neg_idx,
            })
            logger.info("FinBERT loaded (pos=%d, neg=%d)", pos_idx, neg_idx)
            return True

        except Exception as e:
            logger.warning("FinBERT load failed — falling back to VADER: %s", e)
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _state.update({
                "loaded": True, "backend": "vader",
                "vader": SentimentIntensityAnalyzer(),
            })
            return False


def backend() -> str:
    """Returns 'finbert' or 'vader' (after first call to _load)."""
    _load()
    return _state["backend"]


def score_batch(texts: Iterable[str]) -> list[float]:
    """Score a batch of texts; returns compound scores in [-1, 1]."""
    items = [t or "" for t in texts]
    if not items:
        return []

    if not _load():
        # VADER fallback
        v = _state["vader"]
        return [float(v.polarity_scores(t)["compound"]) for t in items]

    torch = _state["torch"]
    tok = _state["tokenizer"]
    model = _state["model"]
    pos, neg = _state["pos_idx"], _state["neg_idx"]

    out: list[float] = []
    with torch.no_grad():
        for i in range(0, len(items), BATCH_SIZE):
            chunk = items[i : i + BATCH_SIZE]
            enc = tok(chunk, padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1)
            # Avoid .numpy() — torch 2.2 was built against numpy 1.x and breaks
            # at runtime when paired with numpy 2.x. .tolist() goes direct.
            compound = (probs[:, pos] - probs[:, neg]).cpu().tolist()
            out.extend(float(x) for x in compound)
    return out


def score(text: str) -> float:
    return score_batch([text])[0]
