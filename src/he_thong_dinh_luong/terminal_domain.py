"""Decision-oriented presentation model for the local trading terminal.

The terminal consumes immutable artifacts and converts them into a compact set of
messages.  It never changes model scores and never upgrades research eligibility.
"""
from __future__ import annotations

from math import isfinite
from typing import Mapping, Sequence

from .portfolio_safety import action_label


def _float(value: object, default: float = 0.0) -> float:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _metric(model: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = model.get(name)
    return value if isinstance(value, Mapping) else {}


def model_grade(model: Mapping[str, object]) -> dict[str, str]:
    champion = str(model.get("champion_model") or "—")
    robust = _metric(model, "robust_reference_validation")
    momentum = _metric(model, "momentum_validation")
    robust_status = str(model.get("robust_validation_status") or "NOT_AVAILABLE")
    robust_ic = _float(robust.get("mean_rank_ic"))
    robust_return = _float(robust.get("top_k_relative_return_after_cost_estimate"), _float(robust.get("top_k_relative_return")))
    momentum_ic = _float(momentum.get("mean_rank_ic"))
    if robust_status == "PASS" and robust_ic > 0.03 and robust_return > 0:
        return {
            "grade": "GREEN",
            "label": "Có tín hiệu tham khảo rõ",
            "detail": f"Robust Rank IC {robust_ic:.3f}, Top-K sau chi phí dương; champion {champion}.",
        }
    if max(robust_ic, momentum_ic) > 0 and robust_return >= 0:
        return {
            "grade": "AMBER",
            "label": "Chỉ dùng làm watchlist",
            "detail": "Tín hiệu đúng chiều nhưng bằng chứng còn yếu hoặc chưa ổn định qua các kỳ.",
        }
    return {
        "grade": "RED",
        "label": "Chưa chứng minh được alpha",
        "detail": "Rank IC/Top-K OOS chưa đạt; không dùng điểm model như xác suất tăng giá.",
    }


def data_grade(manifest: Mapping[str, object], quality: Mapping[str, object]) -> dict[str, str]:
    coverage = _float(manifest.get("primary_coverage"), _float(quality.get("primary_coverage")))
    status = str(manifest.get("data_status") or quality.get("data_status") or "FINAL")
    source_errors = int(_float(quality.get("source_error_count")))
    if coverage >= 0.95 and source_errors == 0:
        label = "Dữ liệu đạt"
        grade = "GREEN" if status == "FINAL" else "AMBER"
        detail = f"Coverage {coverage * 100:.1f}% · {status}."
    elif coverage >= 0.90:
        grade, label = "AMBER", "Dữ liệu còn thiếu"
        detail = f"Coverage {coverage * 100:.1f}% · cần thận trọng khi xếp hạng toàn thị trường."
    else:
        grade, label = "RED", "Dữ liệu không đủ"
        detail = f"Coverage {coverage * 100:.1f}% · không dùng để phân bổ vốn."
    return {"grade": grade, "label": label, "detail": detail}


def _position_reason(row: Mapping[str, object]) -> str:
    reasons: list[str] = []
    if not _bool(row.get("above_ma250")):
        reasons.append("dưới MA250")
    return20 = _float(row.get("return_20"))
    return60 = _float(row.get("return_60"))
    if return20 < 0:
        reasons.append(f"20 phiên {return20 * 100:.1f}%")
    if return60 < 0:
        reasons.append(f"60 phiên {return60 * 100:.1f}%")
    if _float(row.get("target_weight_pct")) <= 0:
        reasons.append("ngoài target hiện tại")
    if _float(row.get("current_weight_pct")) > 15:
        reasons.append("vượt trần 15%/mã")
    return ", ".join(reasons) or "xu hướng và tỷ trọng chưa phát cảnh báo chính"


def position_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        action = str(row.get("action") or "HOLD_MONITOR")
        output.append({
            "symbol": str(row.get("symbol") or ""),
            "quantity": int(_float(row.get("quantity"))),
            "market_price_vnd": _float(row.get("market_price_vnd")),
            "market_value_vnd": _float(row.get("market_value_vnd")),
            "unrealized_pnl_vnd": _float(row.get("unrealized_pnl_vnd")),
            "unrealized_pnl_pct": _float(row.get("unrealized_pnl_pct")),
            "current_weight_pct": _float(row.get("current_weight_pct")),
            "target_weight_pct": _float(row.get("target_weight_pct")),
            "ranking_rank": int(_float(row.get("ranking_rank"), 9999)),
            "trend_score": _float(row.get("trend_score")),
            "rsi14": _float(row.get("rsi14")),
            "above_ma250": _bool(row.get("above_ma250")),
            "action": action,
            "action_label": action_label(action),
            "reason": _position_reason(row),
        })
    return sorted(output, key=lambda row: (-float(row["current_weight_pct"]), str(row["symbol"])))


def watchlist_rows(
    predictions: Sequence[Mapping[str, object]],
    allocation: Sequence[Mapping[str, object]],
    *,
    limit: int = 5,
) -> list[dict[str, object]]:
    weight_by_symbol = {
        str(row.get("symbol") or ""): _float(row.get("target_weight_pct"), _float(row.get("technical_weight_pct")))
        for row in allocation
    }
    ranked = sorted(
        predictions,
        key=lambda row: (
            int(_float(row.get("ranking_rank"), _float(row.get("champion_rank"), 9999))),
            str(row.get("symbol") or ""),
        ),
    )
    output: list[dict[str, object]] = []
    for row in ranked:
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        selected = _bool(row.get("selected_top_k")) or weight_by_symbol.get(symbol, 0.0) > 0
        if not selected:
            continue
        reasons = []
        if _bool(row.get("above_ma250")):
            reasons.append("trên MA250")
        confidence = _float(row.get("reference_confidence"))
        if confidence > 0:
            reasons.append(f"đồng thuận {confidence * 100:.0f}%")
        volatility = _float(row.get("volatility_60"))
        if volatility > 0:
            reasons.append(f"vol60 {volatility * 100:.1f}%")
        output.append({
            "rank": int(_float(row.get("ranking_rank"), _float(row.get("champion_rank"), 9999))),
            "symbol": symbol,
            "target_weight_pct": weight_by_symbol.get(symbol, 0.0),
            "score": _float(row.get("ranking_score"), _float(row.get("reference_score"))),
            "reason": ", ".join(reasons) or "điểm kỹ thuật tương đối cao",
        })
        if len(output) >= limit:
            break
    return output


def paper_brief(metrics: Mapping[str, object], status_text: str = "") -> dict[str, object]:
    fills = int(_float(metrics.get("fill_count"), _float(metrics.get("fills"))))
    pending = int(_float(metrics.get("pending_order_count"), _float(metrics.get("pending_orders"))))
    nav = _float(metrics.get("latest_nav_vnd"), _float(metrics.get("nav_vnd")))
    if not metrics:
        return {
            "state": "EMPTY",
            "label": "Chưa có sổ paper",
            "detail": "Chạy final EOD để lưu tín hiệu đầu tiên; snapshot trong phiên không tạo fill.",
            "fills": 0,
            "pending": 0,
            "nav_vnd": 0.0,
        }
    if fills == 0:
        detail = status_text.strip() or "Đã có tín hiệu nhưng chưa tới open T+1 để khớp lệnh."
        return {"state": "PENDING", "label": "Đang chờ khớp T+1", "detail": detail, "fills": fills, "pending": pending, "nav_vnd": nav}
    return {
        "state": "ACTIVE",
        "label": "Paper đang theo dõi",
        "detail": f"{fills} fill · {pending} lệnh chờ · kết quả chỉ có ý nghĩa sau đủ số phiên OOS.",
        "fills": fills,
        "pending": pending,
        "nav_vnd": nav,
    }


def build_decision_brief(
    *,
    manifest: Mapping[str, object],
    quality: Mapping[str, object],
    model: Mapping[str, object],
    predictions: Sequence[Mapping[str, object]],
    allocation: Sequence[Mapping[str, object]],
    portfolio_summary: Mapping[str, object],
    portfolio_analysis: Sequence[Mapping[str, object]],
    paper_metrics: Mapping[str, object],
    paper_status_text: str = "",
) -> dict[str, object]:
    positions = position_rows(portfolio_analysis)
    review_count = sum(1 for row in positions if str(row["action"]).startswith("REVIEW"))
    no_add_count = sum(1 for row in positions if str(row["action"]).startswith("NO_ADD"))
    model_state = model_grade(model)
    data_state = data_grade(manifest, quality)
    regime = str(model.get("market_regime") or "—")
    budget = _float(model.get("capital_budget_pct"))
    planner_cash = _float(portfolio_summary.get("planner_cash_vnd"), _float(portfolio_summary.get("safe_planner_cash_vnd")))
    buying_power = _float(portfolio_summary.get("broker_buying_power_vnd"), _float(portfolio_summary.get("available_cash_vnd")))
    actions: list[dict[str, str]] = []
    if regime == "RISK_OFF":
        actions.append({"severity": "warning", "title": "Ưu tiên tiền mặt", "detail": f"Regime RISK_OFF; ngân sách cổ phiếu hiện {budget:.1f}%."})
    else:
        actions.append({"severity": "info", "title": "Giải ngân có chọn lọc", "detail": f"Regime {regime}; ngân sách cổ phiếu {budget:.1f}%."})
    if review_count:
        actions.append({"severity": "negative", "title": f"{review_count} vị thế cần xem xét", "detail": "Ngoài target và dưới MA250; mở bảng danh mục để xem lý do từng mã."})
    elif no_add_count:
        actions.append({"severity": "warning", "title": f"{no_add_count} vị thế không nên mua thêm", "detail": "Đang ngoài target hoặc vượt tỷ trọng mục tiêu."})
    else:
        actions.append({"severity": "positive", "title": "Danh mục chưa có cảnh báo giảm chính", "detail": "Tiếp tục theo dõi trend health và target gap."})
    actions.append({
        "severity": "info" if planner_cash > 0 else "warning",
        "title": f"Tiền planner an toàn: {planner_cash:,.0f} ₫",
        "detail": f"Sức mua broker {buying_power:,.0f} ₫ chỉ để hiển thị, không tự động đưa vào kế hoạch.",
    })
    return {
        "data": data_state,
        "model": model_state,
        "regime": regime,
        "capital_budget_pct": budget,
        "actions": actions,
        "positions": positions,
        "watchlist": watchlist_rows(predictions, allocation),
        "paper": paper_brief(paper_metrics, paper_status_text),
    }
