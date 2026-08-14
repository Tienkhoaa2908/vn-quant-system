"""V47 canonical-month signal và latest-session preview guard.

Canonical C3 chỉ đổi khi có tháng hoàn tất mới. Preview dùng đúng trọng số của
canonical nhưng cập nhật feature theo phiên mới nhất. Preview không tạo tín hiệu
bán và không thay canonical; nó chỉ chặn mua thêm khi mã canonical Top-10 đã mất
eligibility hoặc rơi khỏi preview Top-20.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Mapping, Sequence

from . import c3_model
from .c3_model import (
    _features_for_day,
    _market_rows,
    _signal_days,
    component_weights,
    load_historical_rows,
    rank_features,
    run_model,
)
from .core import load_config, paths, state_db, utc_now

PREVIEW_MODE = "LATEST_SESSION_WITH_CANONICAL_WEIGHTS"
PURCHASE_GUARD_MODE = "CANONICAL_TOP10_AND_PREVIEW_TOP20_ELIGIBLE"


def _ensure_schema(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS preview_snapshots(
            snapshot_id TEXT PRIMARY KEY,
            signature TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            market_day TEXT NOT NULL,
            canonical_signal_day TEXT NOT NULL,
            canonical_run_id TEXT NOT NULL,
            market_risk_on INTEGER NOT NULL,
            weights_json TEXT NOT NULL,
            rows_json TEXT NOT NULL,
            audit_json TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_preview_snapshots_created
        ON preview_snapshots(created_at DESC);
        """
    )


def _latest_signal_run(signal_kind: str) -> dict[str, object] | None:
    with state_db() as db:
        row = db.execute(
            """
            SELECT r.run_id,r.finished_at,k.signal_day,r.details_json
            FROM runs r
            JOIN rankings k ON k.run_id=r.run_id
            WHERE r.status='SUCCESS' AND k.signal_kind=?
            GROUP BY r.run_id,r.finished_at,k.signal_day,r.details_json
            ORDER BY k.signal_day DESC,r.finished_at DESC
            LIMIT 1
            """,
            (signal_kind,),
        ).fetchone()
        if row is None:
            return None
        ranking = [
            dict(item)
            for item in db.execute(
                """
                SELECT * FROM rankings
                WHERE run_id=? AND signal_kind=?
                ORDER BY rank
                """,
                (row["run_id"], signal_kind),
            ).fetchall()
        ]
    return {
        "run_id": str(row["run_id"]),
        "finished_at": str(row["finished_at"]),
        "signal_day": str(row["signal_day"]),
        "ranking": ranking,
        "details": json.loads(str(row["details_json"] or "{}")),
    }


def canonical_refresh_status() -> dict[str, object]:
    p = paths()
    calendar, _, _ = _market_rows(p.market_db)
    expected, latest_day = _signal_days(calendar)
    latest = _latest_signal_run("MONTHLY_CANONICAL")
    actual = str(latest["signal_day"]) if latest else None
    return {
        "status": "READY",
        "expected_signal_day": expected.isoformat(),
        "stored_signal_day": actual,
        "market_day": latest_day.isoformat(),
        "current": actual == expected.isoformat(),
        "run_id": latest.get("run_id") if latest else None,
        "finished_at": latest.get("finished_at") if latest else None,
    }


def ensure_canonical_current() -> dict[str, object]:
    before = canonical_refresh_status()
    if before["current"]:
        return {"status": "ALREADY_CURRENT", "canonical": before}
    report = run_model()
    after = canonical_refresh_status()
    if not after["current"]:
        raise ValueError(
            "CANONICAL_REFRESH_FAILED:"
            f"expected={after['expected_signal_day']},stored={after['stored_signal_day']}"
        )
    return {
        "status": "REFRESHED",
        "canonical": after,
        "model_run_id": report.get("run_id"),
    }


def _preview_ineligibility_reasons(feature: object | None) -> list[str]:
    if feature is None:
        return ["MISSING_EXACT_HISTORY"]
    reasons: list[str] = []
    if not bool(getattr(feature, "above_ma250", False)):
        reasons.append("BELOW_MA250")
    config = load_config().get("model", {})
    if not isinstance(config, Mapping):
        config = {}
    min_adv20 = float(config.get("min_adv20_vnd", 5_000_000_000.0))
    max_zero = int(config.get("max_zero_volume_60", 5))
    if float(getattr(feature, "adv20_vnd", 0.0)) < min_adv20:
        reasons.append("ADV20_BELOW_FLOOR")
    if int(getattr(feature, "zero_volume_60", 0)) > max_zero:
        reasons.append("TOO_MANY_ZERO_VOLUME_DAYS")
    return reasons or ["NOT_ELIGIBLE"]


def _decode_preview_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "snapshot_id": str(row["snapshot_id"]),
        "signature": str(row["signature"]),
        "created_at": str(row["created_at"]),
        "market_day": str(row["market_day"]),
        "canonical_signal_day": str(row["canonical_signal_day"]),
        "canonical_run_id": str(row["canonical_run_id"]),
        "market_risk_on": bool(row["market_risk_on"]),
        "weights": json.loads(str(row["weights_json"])),
        "rows": json.loads(str(row["rows_json"])),
        "audit": json.loads(str(row["audit_json"])),
        "details": json.loads(str(row["details_json"])),
    }


def latest_preview_snapshot() -> dict[str, object] | None:
    with state_db() as db:
        _ensure_schema(db)
        row = db.execute(
            "SELECT * FROM preview_snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return _decode_preview_row(row) if row is not None else None


def refresh_latest_preview() -> dict[str, object]:
    canonical_result = ensure_canonical_current()
    canonical = _latest_signal_run("MONTHLY_CANONICAL")
    if canonical is None:
        raise ValueError("MONTHLY_CANONICAL_MISSING_AFTER_REFRESH")

    p = paths()
    config = load_config()
    model_cfg = config.get("model", {})
    if not isinstance(model_cfg, Mapping):
        model_cfg = {}
    historical, universe = load_historical_rows(p.reference_zip)
    calendar, index, stocks = _market_rows(p.market_db)
    expected_canonical, preview_day = _signal_days(calendar)
    if str(canonical["signal_day"]) != expected_canonical.isoformat():
        raise ValueError("PREVIEW_CANONICAL_SIGNAL_MISMATCH")

    # Khóa trọng số theo canonical để preview chỉ phản ánh feature/price mới.
    weights = component_weights(historical, before_day=expected_canonical)
    features, risk_on = _features_for_day(
        signal_day=preview_day,
        calendar=calendar,
        index=index,
        stocks=stocks,
        universe=universe,
        price_multiplier=float(model_cfg.get("price_multiplier", 1000.0)),
        min_adv20_vnd=float(model_cfg.get("min_adv20_vnd", 5_000_000_000.0)),
        max_zero_volume_60=int(model_cfg.get("max_zero_volume_60", 5)),
    )
    ranking = rank_features(features, weights)
    rank_by_symbol = {
        str(row["symbol"]): int(row["rank"]) for row in ranking
    }
    feature_by_symbol = {
        str(feature.symbol): feature for feature in features
    }
    audit: dict[str, dict[str, object]] = {}
    for symbol in sorted(universe):
        feature = feature_by_symbol.get(symbol)
        rank = rank_by_symbol.get(symbol)
        eligible = bool(feature is not None and feature.eligible)
        audit[symbol] = {
            "symbol": symbol,
            "preview_day": preview_day.isoformat(),
            "rank": rank,
            "eligible": eligible,
            "in_top20": bool(rank is not None and rank <= 20),
            "above_ma250": (
                bool(feature.above_ma250) if feature is not None else False
            ),
            "adv20_vnd": (
                float(feature.adv20_vnd) if feature is not None else None
            ),
            "zero_volume_60": (
                int(feature.zero_volume_60) if feature is not None else None
            ),
            "reasons": (
                [] if eligible else _preview_ineligibility_reasons(feature)
            ),
        }

    signature_payload = {
        "mode": PREVIEW_MODE,
        "market_day": preview_day.isoformat(),
        "canonical_signal_day": expected_canonical.isoformat(),
        "canonical_run_id": canonical["run_id"],
        "weights": weights,
        "ranking": [
            {
                "symbol": row["symbol"],
                "rank": row["rank"],
                "score": round(float(row["score"]), 12),
            }
            for row in ranking
        ],
    }
    signature = sha256(
        json.dumps(
            signature_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    with state_db() as db:
        _ensure_schema(db)
        existing = db.execute(
            "SELECT * FROM preview_snapshots WHERE signature=?",
            (signature,),
        ).fetchone()
    if existing is not None:
        result = _decode_preview_row(existing)
        result["status"] = "ALREADY_CURRENT"
        result["canonical_refresh"] = canonical_result
        return result

    created_at = utc_now()
    snapshot_id = "preview-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    details = {
        "mode": PREVIEW_MODE,
        "model_id": c3_model.MODEL_ID,
        "weight_source": "CANONICAL_SIGNAL_DAY",
        "canonical_refresh": canonical_result,
        "candidate_universe_count": len(universe),
        "feature_complete_count": len(features),
        "eligible_count": len(ranking),
        "research_only": True,
        "changes_canonical": False,
        "creates_trade_plan": False,
    }
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            """
            INSERT INTO preview_snapshots(
                snapshot_id,signature,created_at,market_day,
                canonical_signal_day,canonical_run_id,market_risk_on,
                weights_json,rows_json,audit_json,details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id,
                signature,
                created_at,
                preview_day.isoformat(),
                expected_canonical.isoformat(),
                str(canonical["run_id"]),
                1 if risk_on else 0,
                json.dumps(weights, ensure_ascii=False, sort_keys=True),
                json.dumps(ranking, ensure_ascii=False, sort_keys=True),
                json.dumps(audit, ensure_ascii=False, sort_keys=True),
                json.dumps(details, ensure_ascii=False, sort_keys=True),
            ),
        )
    result = {
        "status": "REFRESHED",
        "snapshot_id": snapshot_id,
        "signature": signature,
        "created_at": created_at,
        "market_day": preview_day.isoformat(),
        "canonical_signal_day": expected_canonical.isoformat(),
        "canonical_run_id": str(canonical["run_id"]),
        "market_risk_on": risk_on,
        "weights": weights,
        "rows": ranking,
        "audit": audit,
        "details": details,
        "canonical_refresh": canonical_result,
    }
    output = p.outputs / f"{snapshot_id}.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def purchase_guard_map(
    canonical_rows: Sequence[Mapping[str, object]],
    preview: Mapping[str, object],
    *,
    preview_top_n: int = 20,
) -> dict[str, dict[str, object]]:
    audit = preview.get("audit", {})
    if not isinstance(audit, Mapping):
        audit = {}
    result: dict[str, dict[str, object]] = {}
    for canonical in canonical_rows:
        symbol = str(canonical["symbol"])
        observation = audit.get(symbol, {})
        if not isinstance(observation, Mapping):
            observation = {}
        eligible = bool(observation.get("eligible", False))
        preview_rank_raw = observation.get("rank")
        preview_rank = (
            int(preview_rank_raw) if preview_rank_raw is not None else None
        )
        allowed = bool(
            eligible
            and preview_rank is not None
            and preview_rank <= int(preview_top_n)
        )
        if allowed:
            reason = "ALLOWED_CANONICAL_TOP10_PREVIEW_TOP20"
        elif not eligible:
            reason = "BLOCKED_PREVIEW_INELIGIBLE"
        elif preview_rank is None:
            reason = "BLOCKED_PREVIEW_NOT_RANKED"
        else:
            reason = "BLOCKED_PREVIEW_OUTSIDE_TOP20"
        result[symbol] = {
            "symbol": symbol,
            "canonical_rank": int(canonical.get("rank") or 0),
            "preview_rank": preview_rank,
            "preview_eligible": eligible,
            "preview_in_top20": bool(
                preview_rank is not None and preview_rank <= preview_top_n
            ),
            "allowed_to_buy": allowed,
            "reason": reason,
            "preview_reasons": list(observation.get("reasons", [])),
            "above_ma250": bool(observation.get("above_ma250", False)),
            "adv20_vnd": observation.get("adv20_vnd"),
        }
    return result


def apply_preview_purchase_guard(
    plan: Mapping[str, object],
    preview: Mapping[str, object],
) -> dict[str, object]:
    """Reallocate buy orders after applying the latest preview guard.

    Sell review is preserved unchanged because preview is not an exit signal.
    """

    from .weekly_plan import allocate_buy_orders

    result = dict(plan)
    rationale = dict(result.get("rationale") or {})
    raw_candidates = list(rationale.get("buy_candidates", []))
    preview_top_n = int(
        load_config().get("model", {}).get("preview_purchase_guard_top_n", 20)
    )
    guard = purchase_guard_map(
        raw_candidates,
        preview,
        preview_top_n=preview_top_n,
    )
    candidates: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for raw in raw_candidates:
        row = dict(raw)
        observation = dict(guard.get(str(row.get("symbol")), {}))
        row.update(
            {
                "preview_rank": observation.get("preview_rank"),
                "preview_eligible": observation.get("preview_eligible", False),
                "preview_allowed_to_buy": observation.get(
                    "allowed_to_buy", False
                ),
                "preview_guard_reason": observation.get("reason"),
                "preview_guard_details": observation,
            }
        )
        if observation.get("allowed_to_buy"):
            candidates.append(row)
        else:
            blocked.append(row)

    budget = float(result.get("spendable_budget_vnd") or 0.0)
    max_orders = int(rationale.get("maximum_buy_orders") or 1)
    cost_bps = float(rationale.get("planning_cost_bps") or 0.0)
    buy_orders = allocate_buy_orders(
        candidates,
        budget_vnd=budget,
        max_orders=max_orders,
        cost_bps=cost_bps,
    )
    single_order = allocate_buy_orders(
        candidates,
        budget_vnd=budget,
        max_orders=1,
        cost_bps=cost_bps,
    )
    for order in buy_orders + single_order:
        observation = guard.get(str(order["symbol"]), {})
        order.update(
            {
                "preview_rank": observation.get("preview_rank"),
                "preview_eligible": observation.get("preview_eligible"),
                "preview_guard_reason": observation.get("reason"),
                "reason": "CANONICAL_TOP10_PREVIEW_TOP20_AND_UNDERWEIGHT",
            }
        )

    reviews: list[dict[str, object]] = []
    preview_audit = preview.get("audit", {})
    if not isinstance(preview_audit, Mapping):
        preview_audit = {}
    for raw in result.get("position_reviews", []):
        review = dict(raw)
        observation = preview_audit.get(str(review.get("symbol")), {})
        review["preview_observation"] = (
            dict(observation) if isinstance(observation, Mapping) else {}
        )
        review["preview_can_trigger_sell"] = False
        reviews.append(review)

    total = sum(float(row["estimated_cost_vnd"]) for row in buy_orders)
    first = buy_orders[0] if buy_orders else None
    guard_summary = {
        "mode": PURCHASE_GUARD_MODE,
        "preview_snapshot_id": preview.get("snapshot_id"),
        "preview_day": preview.get("market_day"),
        "canonical_signal_day": preview.get("canonical_signal_day"),
        "preview_top_n": preview_top_n,
        "canonical_candidate_count": len(raw_candidates),
        "allowed_candidate_count": len(candidates),
        "blocked_candidate_count": len(blocked),
        "blocked": [
            {
                "symbol": row.get("symbol"),
                "canonical_rank": row.get("rank"),
                "preview_rank": row.get("preview_rank"),
                "reason": row.get("preview_guard_reason"),
                "details": row.get("preview_guard_details"),
            }
            for row in blocked
        ],
        "sell_policy_changed": False,
    }
    rationale.update(
        {
            "buy_candidates": candidates + blocked,
            "buy_orders": buy_orders,
            "single_order_baseline": single_order,
            "position_reviews": reviews,
            "preview_purchase_guard": guard_summary,
            "preview_snapshot_id": preview.get("snapshot_id"),
            "preview_market_day": preview.get("market_day"),
            "preview_canonical_signal_day": preview.get(
                "canonical_signal_day"
            ),
            "preview_weights": preview.get("weights"),
        }
    )
    result.update(
        {
            "buy_orders": buy_orders,
            "single_order_baseline": single_order,
            "position_reviews": reviews,
            "buy_symbol": str(first["symbol"]) if first else None,
            "buy_quantity": int(first["quantity"]) if first else 0,
            "estimated_buy_value_vnd": total,
            "remaining_budget_vnd": max(budget - total, 0.0),
            "preview_purchase_guard": guard_summary,
            "preview_snapshot_id": preview.get("snapshot_id"),
            "preview_signal_day": preview.get("market_day"),
            "rationale": rationale,
        }
    )
    return result


def signal_refresh_status() -> dict[str, object]:
    canonical = canonical_refresh_status()
    preview = latest_preview_snapshot()
    return {
        "canonical": canonical,
        "preview": (
            {
                "snapshot_id": preview["snapshot_id"],
                "created_at": preview["created_at"],
                "market_day": preview["market_day"],
                "canonical_signal_day": preview["canonical_signal_day"],
                "current": preview["market_day"] == canonical["market_day"],
            }
            if preview
            else None
        ),
        "purchase_guard_mode": PURCHASE_GUARD_MODE,
    }
