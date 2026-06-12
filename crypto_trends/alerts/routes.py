"""FastAPI routes for managing user alert rules.

Free tier capped at FREE_RULE_CAP. Pro/founder unlimited. All mutations
auth-required. Reads return only the requesting user's rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import current_user, is_pro
from crypto_trends.auth.models import AlertEvent, AlertRule, User

router = APIRouter(prefix="/alerts", tags=["alerts"])

ALLOWED_CONDITIONS = {"score_above", "score_below", "price_above", "price_below"}
FREE_RULE_CAP = 3


class AlertRuleIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    asset_class: str = Field(min_length=1, max_length=32)
    condition: str
    threshold: float
    note: Optional[str] = Field(default=None, max_length=200)
    enabled: bool = True


class AlertRuleOut(BaseModel):
    id: int
    symbol: str
    asset_class: str
    condition: str
    threshold: float
    note: Optional[str]
    enabled: bool
    created_at: datetime
    last_triggered_at: Optional[datetime]


class AlertEventOut(BaseModel):
    id: int
    rule_id: int
    triggered_at: datetime
    observed_value: float
    email_sent: bool


def _to_out(r: AlertRule) -> AlertRuleOut:
    return AlertRuleOut(
        id=r.id or 0,
        symbol=r.symbol,
        asset_class=r.asset_class,
        condition=r.condition,
        threshold=r.threshold,
        note=r.note,
        enabled=r.enabled,
        created_at=r.created_at,
        last_triggered_at=r.last_triggered_at,
    )


@router.get("", response_model=list[AlertRuleOut])
def list_rules(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[AlertRuleOut]:
    if user is None:
        raise HTTPException(401, "Not authenticated")
    rows = session.exec(
        select(AlertRule).where(AlertRule.user_id == user.id).order_by(AlertRule.created_at.desc())
    ).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=AlertRuleOut, status_code=201)
def create_rule(
    payload: AlertRuleIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> AlertRuleOut:
    if user is None:
        raise HTTPException(401, "Not authenticated")
    if payload.condition not in ALLOWED_CONDITIONS:
        raise HTTPException(
            422,
            f"Invalid condition. Must be one of: {sorted(ALLOWED_CONDITIONS)}",
        )
    # Free-tier cap (founder + pro unlimited)
    if not is_pro(user):
        existing = session.exec(
            select(AlertRule).where(
                (AlertRule.user_id == user.id) & (AlertRule.enabled == True)  # noqa: E712
            )
        ).all()
        if len(existing) >= FREE_RULE_CAP:
            raise HTTPException(
                402,
                f"Free tier limited to {FREE_RULE_CAP} active alerts. "
                f"Upgrade to Pro for unlimited alerts.",
            )
    rule = AlertRule(
        user_id=user.id or 0,
        symbol=payload.symbol.upper(),
        asset_class=payload.asset_class,
        condition=payload.condition,
        threshold=payload.threshold,
        note=payload.note,
        enabled=payload.enabled,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return _to_out(rule)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> None:
    if user is None:
        raise HTTPException(401, "Not authenticated")
    rule = session.get(AlertRule, rule_id)
    if rule is None or rule.user_id != user.id:
        raise HTTPException(404, "Alert rule not found")
    session.delete(rule)
    session.commit()


@router.patch("/{rule_id}", response_model=AlertRuleOut)
def toggle_rule(
    rule_id: int,
    enabled: bool,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> AlertRuleOut:
    if user is None:
        raise HTTPException(401, "Not authenticated")
    rule = session.get(AlertRule, rule_id)
    if rule is None or rule.user_id != user.id:
        raise HTTPException(404, "Alert rule not found")
    rule.enabled = enabled
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return _to_out(rule)


@router.get("/events", response_model=list[AlertEventOut])
def list_events(
    limit: int = 20,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[AlertEventOut]:
    """Recent trigger history — useful 'why did I not get an alert' debug
    and a 'recently triggered' feed on the frontend."""
    if user is None:
        raise HTTPException(401, "Not authenticated")
    limit = max(1, min(limit, 100))
    rows = session.exec(
        select(AlertEvent)
        .where(AlertEvent.user_id == user.id)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(limit)
    ).all()
    return [
        AlertEventOut(
            id=r.id or 0,
            rule_id=r.rule_id,
            triggered_at=r.triggered_at,
            observed_value=r.observed_value,
            email_sent=r.email_sent,
        )
        for r in rows
    ]
