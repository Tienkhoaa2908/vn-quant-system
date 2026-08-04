"""Tổng quan thị trường chỉ đọc cho V47.

Trang này tách rõ canonical tháng và latest-session preview. Nó không tạo plan,
không thay shadow và không gửi lệnh. Preview chỉ là lớp quan sát/purchase guard.
"""
from __future__ import annotations

import sqlite3
from typing import Mapping

from .broker_portfolio import latest_broker_portfolio
from .core import load_config, paths, state_db
from .signal_refresh import (
    canonical_refresh_status,
    latest_preview_snapshot,
    purchase_guard_map,
    signal_refresh_status,
)


def _latest_two_runs() -> list[dict[str, object]]:
    with state_db() as db:
        runs = [
            dict(row)
            for row in db.execute(
                """
                SELECT r.run_id,r.finished_at,k.signal_day
                FROM runs r
                JOIN rankings k ON k.run_id=r.run_id
                WHERE r.status='SUCCESS'
                  AND k.signal_kind='MONTHLY_CANONICAL'
                GROUP BY r.run_id,r.finished_at,k.signal_day
                ORDER BY k.signal_day DESC,r.finished_at DESC
                LIMIT 50
                """
            ).fetchall()
        ]
        for run in runs:
            run["ranking"] = [
                dict(row)
                for row in db.execute(
                    """
                    SELECT * FROM rankings
                    WHERE run_id=? AND signal_kind='MONTHLY_CANONICAL'
                    ORDER BY rank
                    """,
                    (run["run_id"],),
                ).fetchall()
            ]
    # Có thể có nhiều run cùng signal_day do các bản cũ chạy lại C3. Chỉ giữ
    # signal_day khác nhau để rank_change thực sự là thay đổi theo tháng.
    distinct: list[dict[str, object]] = []
    seen: set[str] = set()
    for run in runs:
        day = str(run["signal_day"])
        if day in seen:
            continue
        seen.add(day)
        distinct.append(run)
        if len(distinct) >= 2:
            break
    return distinct


def _index_regime() -> dict[str, object]:
    db = sqlite3.connect(paths().market_db)
    try:
        rows = db.execute(
            """
            SELECT day,close FROM bars
            WHERE upper(asset_type)='INDEX'
              AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
            ORDER BY day DESC LIMIT 250
            """
        ).fetchall()
    finally:
        db.close()
    if not rows:
        return {"status": "MISSING"}
    latest_day, latest_close = rows[0]
    ma250 = sum(float(row[1]) for row in rows) / len(rows)
    return {
        "status": "READY",
        "market_day": str(latest_day),
        "vnindex_close": float(latest_close),
        "ma250": ma250,
        "market_risk_on": bool(
            len(rows) >= 250 and float(latest_close) >= ma250
        ),
        "session_count": len(rows),
        "distance_to_ma250": (
            float(latest_close) / ma250 - 1.0 if ma250 > 0 else None
        ),
    }


def market_overview(limit: int = 30) -> dict[str, object]:
    bounded = min(max(int(limit), 1), 100)
    runs = _latest_two_runs()
    status = signal_refresh_status()
    if not runs:
        return {
            "status": "MISSING_RANKING",
            "message": "Chưa có canonical C3 ranking. Chạy canonical tháng trước.",
            "canonical_rows": [],
            "preview_rows": [],
            "rows": [],
            "market": _index_regime(),
            "signal_status": status,
        }

    latest = runs[0]
    previous = runs[1] if len(runs) > 1 else None
    previous_rank = {
        str(row["symbol"]): int(row["rank"])
        for row in (previous or {}).get("ranking", [])
    }
    broker = latest_broker_portfolio()
    held = {
        str(row["symbol"]): int(row["quantity"])
        for row in (broker or {}).get("positions", [])
    }
    preview = latest_preview_snapshot()
    preview_rank = {
        str(row["symbol"]): int(row["rank"])
        for row in (preview or {}).get("rows", [])
    }
    preview_audit = (preview or {}).get("audit", {})
    if not isinstance(preview_audit, Mapping):
        preview_audit = {}

    canonical_rows: list[dict[str, object]] = []
    for raw in latest["ranking"][:bounded]:
        row = dict(raw)
        symbol = str(row["symbol"])
        prior = previous_rank.get(symbol)
        observation = preview_audit.get(symbol, {})
        if not isinstance(observation, Mapping):
            observation = {}
        row.update(
            {
                "previous_rank": prior,
                "rank_change": (
                    prior - int(row["rank"]) if prior is not None else None
                ),
                "held_quantity": held.get(symbol, 0),
                "in_top10": int(row["rank"]) <= 10,
                "in_top20": int(row["rank"]) <= 20,
                "preview_rank": preview_rank.get(symbol),
                "preview_eligible": bool(
                    observation.get("eligible", False)
                ),
                "preview_reasons": list(
                    observation.get("reasons", [])
                ),
            }
        )
        canonical_rows.append(row)

    canonical_rank = {
        str(row["symbol"]): int(row["rank"])
        for row in latest["ranking"]
    }
    preview_rows: list[dict[str, object]] = []
    for raw in (preview or {}).get("rows", [])[:bounded]:
        row = dict(raw)
        symbol = str(row["symbol"])
        row.update(
            {
                "canonical_rank": canonical_rank.get(symbol),
                "held_quantity": held.get(symbol, 0),
                "is_canonical_top10": bool(
                    canonical_rank.get(symbol) is not None
                    and canonical_rank[symbol] <= 10
                ),
            }
        )
        preview_rows.append(row)

    guard = (
        purchase_guard_map(
            latest["ranking"][:10],
            preview,
            preview_top_n=int(
                load_config().get("model", {}).get(
                    "preview_purchase_guard_top_n", 20
                )
            ),
        )
        if preview
        else {}
    )
    model_cfg = load_config().get("model", {})
    if not isinstance(model_cfg, Mapping):
        model_cfg = {}
    return {
        "status": "SUCCESS",
        "mode": "READ_ONLY_CANONICAL_AND_PREVIEW_OVERVIEW",
        "creates_trade_plan": False,
        "ranking_frequency": model_cfg.get(
            "canonical_frequency", "MONTHLY"
        ),
        "model_id": model_cfg.get("model_id"),
        "run": {
            key: latest[key]
            for key in ("run_id", "finished_at", "signal_day")
        },
        "previous_run": (
            {
                key: previous[key]
                for key in ("run_id", "finished_at", "signal_day")
            }
            if previous
            else None
        ),
        "preview": (
            {
                "snapshot_id": preview["snapshot_id"],
                "created_at": preview["created_at"],
                "market_day": preview["market_day"],
                "canonical_signal_day": preview[
                    "canonical_signal_day"
                ],
                "market_risk_on": preview["market_risk_on"],
            }
            if preview
            else None
        ),
        "signal_status": status,
        "canonical_status": canonical_refresh_status(),
        "market": _index_regime(),
        "canonical_rows": canonical_rows,
        "preview_rows": preview_rows,
        "rows": canonical_rows,
        "top10": canonical_rows[:10],
        "purchase_guard": guard,
        "broker_snapshot_id": (broker or {}).get("snapshot_id"),
        "research_only": True,
    }
