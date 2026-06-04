"""ensemble_v1 — momentum + news sentiment combined, with a negative-event veto.

Inputs:
  - momentum_v1 score per symbol (already cross-sectionally normalized)
  - news_v1 sentiment per symbol (already z-scored within the asset class)

Output:
  - per-symbol score in [-1, 1]
  - explicit veto when negative_event is True (long-leg score capped or removed)

Important caveat on backtesting this signal: we only persist news headlines
from the time we started ingesting (no historical archive), so the ensemble's
backtest reflects only the momentum portion before that date. The news
contribution can only be evaluated going forward (paper-trade).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from crypto_trends.signals.news import NewsSignal

SIGNAL_NAME = "ensemble_v1"


@dataclass(frozen=True)
class EnsembleWeights:
    momentum: float = 0.70
    news_sentiment: float = 0.30
    negative_event_penalty: float = 0.50  # multiplicative drag on positive scores


def combine(
    momentum_score: float,
    news: NewsSignal | None,
    weights: EnsembleWeights = EnsembleWeights(),
) -> float:
    """Blend a momentum score with a NewsSignal for one symbol.

    Returns a value in roughly [-1, 1]. If `news` is None (no headlines),
    we fall back to the momentum score alone.
    """
    if news is None:
        return float(momentum_score)

    # Clip the news sentiment z-score so a single outlier headline doesn't
    # dominate the blend.
    sent_clipped = float(np.tanh(news.sentiment_z / 2.0))

    blended = (
        weights.momentum * momentum_score
        + weights.news_sentiment * sent_clipped
    ) / (weights.momentum + weights.news_sentiment)

    if news.negative_event and blended > 0:
        # Penalize *long* signals on names with flagged negative news. Don't
        # boost shorts symmetrically — bad-news shorts are well-served by raw
        # momentum already, and the penalty mainly exists to prevent buying
        # into a known landmine.
        blended *= (1.0 - weights.negative_event_penalty)

    return float(blended)
