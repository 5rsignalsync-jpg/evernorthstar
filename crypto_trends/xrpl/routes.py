"""Public read-only endpoint for the XRPL adoption tracker.

Returns the latest row per metric_key from xrpl_metrics. Consumed by
web/app/xrpl/page.tsx via server-side fetch with 30-minute ISR.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from crypto_trends.data.store import connect

log = logging.getLogger(__name__)
router = APIRouter(prefix="/xrpl", tags=["xrpl"])


class MetricOut(BaseModel):
    metric_key: str
    value_text: str
    value_numeric: Optional[float] = None
    sub_text: Optional[str] = None
    source: Optional[str] = None
    as_of_date: Optional[date] = None
    fetched_at: datetime


class MetricsResponse(BaseModel):
    metrics: dict[str, MetricOut]
    # Most-recent fetched_at across all keys. The page shows this as
    # "Data as of ..." so the viewer can judge freshness.
    last_refresh: Optional[datetime] = None


@router.get("/metrics", response_model=MetricsResponse)
def get_latest_metrics() -> MetricsResponse:
    """Return latest value per metric_key.

    Uses a window function to pick the most recent row for each key
    in a single query. Empty table → empty metrics dict (the frontend
    falls back to its own hard-coded constants).
    """
    try:
        with connect(read_only=True) as conn:
            rows = conn.execute(
                """SELECT metric_key, value_text, value_numeric, sub_text,
                          source, as_of_date, fetched_at
                   FROM (
                     SELECT *,
                       ROW_NUMBER() OVER (PARTITION BY metric_key
                                          ORDER BY fetched_at DESC) AS rn
                     FROM xrpl_metrics
                   ) WHERE rn = 1"""
            ).fetchall()
    except Exception as e:
        # Table likely doesn't exist yet (new deploy, schema not applied).
        # Return empty so the page uses its fallback constants.
        log.warning("xrpl.get_latest_metrics: query failed: %s", e)
        return MetricsResponse(metrics={}, last_refresh=None)

    metrics: dict[str, MetricOut] = {}
    latest_fetched: Optional[datetime] = None
    for key, vt, vn, st, src, as_of, fetched in rows:
        metrics[key] = MetricOut(
            metric_key=key,
            value_text=vt,
            value_numeric=vn,
            sub_text=st,
            source=src,
            as_of_date=as_of,
            fetched_at=fetched,
        )
        if latest_fetched is None or fetched > latest_fetched:
            latest_fetched = fetched

    return MetricsResponse(metrics=metrics, last_refresh=latest_fetched)
