"""Tổng quan thị trường chỉ đọc cho V46.

Trang này dùng canonical monthly C3 ranking để người dùng kiểm tra thị trường và
Top cổ phiếu bất kỳ lúc nào. Nó không tạo plan, không ghi lệnh và không thay đổi
performance shadow.
"""
from __future__ import annotations

import sqlite3
from typing import Mapping

from .broker_portfolio import latest_broker_portfolio
from .core import load_config, paths, state_db


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
                ORDER BY r.finished_at DESC
                LIMIT 2
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
    return runs


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
        "market_risk_on": bool(len(rows) >= 250 and float(latest_close) >= ma250),
        "session_count": len(rows),
        "distance_to_ma250": float(latest_close) / ma250 - 1.0 if ma250 > 0 else None,
    }


def market_overview(limit: int = 30) -> dict[str, object]:
    bounded = min(max(int(limit), 1), 100)
    runs = _latest_two_runs()
    if not runs:
        return {
            "status": "MISSING_RANKING",
            "message": "Chưa có canonical C3 ranking. Chạy C3 trước.",
            "rows": [],
            "market": _index_regime(),
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
    rows: list[dict[str, object]] = []
    for raw in latest["ranking"][:bounded]:
        row = dict(raw)
        symbol = str(row["symbol"])
        prior = previous_rank.get(symbol)
        row["previous_rank"] = prior
        row["rank_change"] = prior - int(row["rank"]) if prior is not None else None
        row["held_quantity"] = held.get(symbol, 0)
        row["in_top10"] = int(row["rank"]) <= 10
        row["in_top20"] = int(row["rank"]) <= 20
        rows.append(row)
    model_cfg = load_config().get("model", {})
    if not isinstance(model_cfg, Mapping):
        model_cfg = {}
    return {
        "status": "SUCCESS",
        "mode": "READ_ONLY_MARKET_OVERVIEW",
        "creates_trade_plan": False,
        "ranking_frequency": model_cfg.get("canonical_frequency", "MONTHLY"),
        "model_id": model_cfg.get("model_id"),
        "run": {key: latest[key] for key in ("run_id", "finished_at", "signal_day")},
        "previous_run": (
            {key: previous[key] for key in ("run_id", "finished_at", "signal_day")}
            if previous
            else None
        ),
        "market": _index_regime(),
        "rows": rows,
        "top10": rows[:10],
        "broker_snapshot_id": (broker or {}).get("snapshot_id"),
        "research_only": True,
    }
