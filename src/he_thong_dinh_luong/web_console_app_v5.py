"""VN Quant Local Terminal v5.

The primary workflow is intentionally one page: update, read the action centre,
inspect the live portfolio, allocate new cash and monitor paper trading without
switching tabs.  Advanced diagnostics remain available lower on the same page.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from . import web_console_app_v3 as base
from .dnse_portfolio import DnseReadOnlyClient, list_masked_accounts
from .dnse_portfolio_v2 import sync_portfolio
from .portfolio_planner import (
    Holding,
    PlanRequest,
    PortfolioStore,
    build_incremental_plan,
    latest_price_map,
)
from .terminal_domain import build_decision_brief
from .web_local_core import (
    JobStore,
    LocalWebConfig,
    PipelineStep,
    execute_job,
    latest_paper_snapshot,
    load_paper_nav,
    load_paper_positions,
    read_log_tail,
)

NICEGUI_VERSION = "3.14.0"
APP_TITLE = "VN Quant Local Terminal"
VN_TZ = timezone(timedelta(hours=7))


def _parser() -> argparse.ArgumentParser:
    return base._parser()


def _json(path: Path) -> dict[str, object]:
    return base._json(path)


def _csv(path: Path, *, limit: int = 1000) -> list[dict[str, str]]:
    return base._csv(path, limit=limit)


def _vnd(value: object) -> str:
    return base._vnd(value)


def _pct(value: object, *, already_percent: bool = False) -> str:
    return base._percent(value, already_percent=already_percent)


def _num(value: object, digits: int = 2) -> str:
    return base._number(value, digits)


def _latest_portfolio_snapshot(data_root: Path) -> Path | None:
    pointer = data_root / "dnse-portfolio-live" / "LATEST.txt"
    if not pointer.is_file():
        return None
    try:
        path = Path(pointer.read_text(encoding="utf-8").strip())
    except OSError:
        return None
    return path if path.is_dir() else None


def _paper_status(snapshot: Path | None) -> str:
    if snapshot is None:
        return ""
    path = snapshot / "paper_status.txt"
    try:
        return path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""


def _columns(spec: Sequence[tuple[str, str]]) -> list[dict[str, object]]:
    return [
        {"name": field, "label": label, "field": field, "sortable": True, "align": "left"}
        for field, label in spec
    ]


def _present_positions(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "symbol": row.get("symbol"),
            "quantity": row.get("quantity"),
            "market_price": _vnd(row.get("market_price_vnd")),
            "market_value": _vnd(row.get("market_value_vnd")),
            "pnl": _vnd(row.get("unrealized_pnl_vnd")),
            "pnl_pct": _pct(row.get("unrealized_pnl_pct")),
            "weight": _pct(row.get("current_weight_pct"), already_percent=True),
            "target": _pct(row.get("target_weight_pct"), already_percent=True),
            "trend": _pct(row.get("trend_score")),
            "action": row.get("action_label"),
            "reason": row.get("reason"),
        }
        for row in rows
    ]


def _present_watchlist(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "rank": row.get("rank"),
            "symbol": row.get("symbol"),
            "target": _pct(row.get("target_weight_pct"), already_percent=True),
            "score": _num(row.get("score"), 3),
            "reason": row.get("reason"),
        }
        for row in rows
    ]


def _latest_bundle(config: LocalWebConfig) -> tuple[Path, dict[str, Path], dict[str, object], dict[str, object], dict[str, object], list[dict[str, str]], list[dict[str, str]]]:
    run = base._latest_analysis(config.data_root)
    if run is None:
        raise ValueError("CHUA_CO_KET_QUA_PHAN_TICH")
    paths = base._analysis_paths(run)
    return (
        run,
        paths,
        _json(paths["manifest"]),
        _json(paths["quality"]),
        _json(paths["model"]),
        _csv(paths["prediction"], limit=1000),
        _csv(paths["allocation"], limit=200),
    )


def build_app(ui: Any, config: LocalWebConfig, jobs: JobStore, portfolio: PortfolioStore) -> None:
    ui.colors(primary="#0b1f33", secondary="#1d3b55", accent="#0f8b8d", positive="#15803d", negative="#b91c1c", warning="#b45309")
    ui.add_css("""
        body { background:#eef2f6; color:#13283a; font-family:Inter,Segoe UI,Arial,sans-serif; }
        .terminal-shell { max-width:1780px; margin:0 auto; }
        .sidebar { width:240px; min-width:240px; min-height:calc(100vh - 64px); background:#0b1f33; color:white; position:sticky; top:64px; align-self:flex-start; }
        .nav-button { width:100%; justify-content:flex-start; color:#dbe7f1; border-radius:8px; }
        .nav-button:hover { background:#18344d; }
        .content { min-width:0; flex:1; }
        .surface { background:white; border:1px solid #dbe4ec; border-radius:12px; box-shadow:0 4px 14px rgba(15,35,55,.05); }
        .metric { min-width:180px; flex:1 1 180px; padding:18px; }
        .metric-value { font-size:1.45rem; font-weight:760; color:#102a43; line-height:1.25; }
        .metric-note { color:#627d98; font-size:.78rem; }
        .section-title { font-size:1.18rem; font-weight:760; color:#102a43; }
        .section-subtitle { color:#627d98; font-size:.9rem; }
        .action-card { min-height:126px; flex:1 1 300px; }
        .action-positive { border-left:5px solid #15803d; }
        .action-warning { border-left:5px solid #b45309; }
        .action-negative { border-left:5px solid #b91c1c; }
        .action-info { border-left:5px solid #0f8b8d; }
        .sticky-command { position:sticky; top:72px; z-index:20; }
        .mono textarea { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
        .compact-table .q-table th { background:#f5f8fb; color:#334e68; font-weight:700; }
        .compact-table .q-table td { white-space:normal; }
        .grade-green { color:#15803d; font-weight:700; }
        .grade-amber { color:#b45309; font-weight:700; }
        .grade-red { color:#b91c1c; font-weight:700; }
        @media (max-width:1100px) { .sidebar { display:none; } }
    """)
    refs: dict[str, Any] = {}
    state: dict[str, object] = {
        "accounts": {},
        "last_job": None,
        "syncing": False,
        "auto_sync_job": None,
        "last_plan": None,
    }

    def scroll(target: str) -> None:
        ui.run_javascript(f"document.getElementById('{target}').scrollIntoView({{behavior:'smooth',block:'start'}})")

    def metric(title: str, key: str, note: str = "") -> None:
        with ui.card().classes("surface metric"):
            ui.label(title).classes("text-caption text-grey-7")
            refs[key] = ui.label("—").classes("metric-value")
            refs[f"{key}_note"] = ui.label(note).classes("metric-note")

    def section_title(title: str, subtitle: str = "") -> None:
        ui.label(title).classes("section-title")
        if subtitle:
            ui.label(subtitle).classes("section-subtitle")

    with ui.header().classes("h-16 items-center justify-between bg-primary text-white px-5"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("candlestick_chart", size="32px")
            with ui.column().classes("gap-0"):
                ui.label(APP_TITLE).classes("text-h6")
                ui.label("DNSE read-only · phân tích kỹ thuật · phân bổ vốn · paper OOS").classes("text-caption text-blue-1")
        with ui.row().classes("items-center gap-3"):
            refs["header_connection"] = ui.badge("DNSE chưa kiểm tra", color="warning").props("outline")
            refs["header_data"] = ui.badge("Chưa có dữ liệu", color="grey").props("outline")
            refs["header_clock"] = ui.label(datetime.now(VN_TZ).strftime("%H:%M:%S")).classes("text-caption")

    with ui.row().classes("terminal-shell w-full no-wrap items-start"):
        with ui.column().classes("sidebar p-4 gap-2"):
            ui.label("ĐIỀU HƯỚNG").classes("text-caption text-blue-2 px-2 mb-1")
            for label, icon, target in (
                ("Tổng quan", "space_dashboard", "overview"),
                ("Danh mục", "account_balance_wallet", "portfolio"),
                ("Tiền mới", "payments", "capital"),
                ("Tín hiệu", "leaderboard", "signals"),
                ("Paper trading", "receipt_long", "paper"),
                ("Kiểm định", "science", "research"),
                ("Vận hành", "terminal", "operations"),
            ):
                ui.button(label, icon=icon, on_click=lambda target=target: scroll(target)).props("flat no-caps").classes("nav-button")
            ui.separator().classes("bg-blue-grey-7 my-3")
            ui.label("KẾT NỐI DNSE").classes("text-caption text-blue-2 px-2")
            refs["account_select"] = ui.select({}, label="Tiểu khoản").props("dark outlined dense").classes("w-full")
            refs["connect_button"] = ui.button("XÁC THỰC OPENAPI", icon="link").props("outline no-caps color=white").classes("w-full")
            refs["sync_button_side"] = ui.button("ĐỒNG BỘ DANH MỤC", icon="sync").props("unelevated no-caps color=accent").classes("w-full")
            refs["connection_note"] = ui.label("Dùng API Key/Secret local; không nhập mật khẩu DNSE.").classes("text-caption text-blue-1")

        with ui.column().classes("content p-5 gap-5"):
            with ui.card().classes("surface sticky-command w-full p-4").props("id=overview"):
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
                    with ui.column().classes("gap-1"):
                        ui.label("Trung tâm hành động").classes("text-h5 text-weight-bold")
                        refs["command_summary"] = ui.label("Bấm cập nhật để lấy dữ liệu mới, chạy model và đồng bộ danh mục trên cùng một màn hình.").classes("text-body2 text-grey-7")
                    with ui.row().classes("items-center gap-3"):
                        refs["run_mode"] = ui.select({
                            "auto": "Tự động",
                            "snapshot": "Snapshot ngay",
                            "final": "Final EOD",
                        }, value="auto", label="Chế độ").props("outlined dense").classes("w-44")
                        refs["run_button"] = ui.button("CẬP NHẬT & PHÂN TÍCH", icon="play_arrow").props("unelevated size=lg no-caps color=accent")
                refs["progress"] = ui.linear_progress(value=0, show_value=False).props("indeterminate").classes("hidden w-full mt-3")
                refs["job_status"] = ui.label("Hệ thống đang rảnh.").classes("text-caption text-grey-7 mt-2")

            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric("Thị trường", "market_regime", "Regime và ngân sách vốn")
                metric("Dữ liệu", "data_grade", "Coverage và finality")
                metric("Chất lượng model", "model_grade", "Bằng chứng OOS")
                metric("Tài sản ròng", "portfolio_nav", "Danh mục DNSE")
                metric("Tiền planner", "planner_cash", "Không dùng sức mua chưa xác minh")
                metric("Paper NAV", "paper_nav", "OOS sống")

            with ui.row().classes("w-full gap-4 flex-wrap"):
                for index in range(3):
                    with ui.card().classes("surface action-card p-4 action-info") as card:
                        refs[f"action_card_{index}"] = card
                        refs[f"action_title_{index}"] = ui.label("—").classes("text-subtitle1 text-weight-bold")
                        refs[f"action_detail_{index}"] = ui.label("—").classes("text-body2 text-grey-7")

            with ui.card().classes("surface w-full p-4").props("id=portfolio"):
                with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
                    with ui.column().classes("gap-0"):
                        section_title("Danh mục DNSE", "Chỉ hiển thị thông tin có thể hành động; chỉ báo chi tiết nằm trong phần mở rộng.")
                    with ui.row().classes("items-center gap-2"):
                        refs["portfolio_asof"] = ui.label("Chưa đồng bộ").classes("text-caption text-grey-7")
                        refs["sync_button"] = ui.button("Đồng bộ lại", icon="sync").props("outline dense no-caps")
                refs["portfolio_table"] = ui.table(
                    columns=_columns((
                        ("symbol", "Mã"), ("quantity", "SL"), ("market_price", "Giá"),
                        ("market_value", "Giá trị"), ("pnl", "Lãi/lỗ"), ("pnl_pct", "%"),
                        ("weight", "Tỷ trọng"), ("target", "Target"), ("trend", "Trend"),
                        ("action", "Đánh giá"), ("reason", "Lý do"),
                    )),
                    rows=[], row_key="symbol", pagination=15,
                ).classes("w-full compact-table").props("flat bordered dense")
                refs["portfolio_empty"] = ui.label("Chưa có danh mục. Xác thực OpenAPI rồi bấm Đồng bộ danh mục.").classes("text-body2 text-grey-6 p-3")
                with ui.expansion("Chỉ báo chi tiết và giới hạn", icon="analytics").classes("w-full"):
                    refs["portfolio_diagnostics"] = ui.label("—").classes("text-body2")

            with ui.card().classes("surface w-full p-4").props("id=capital"):
                section_title("Phân bổ tiền mới", "Planner dùng target gap, lot, phí, slippage và tiền settled an toàn; không tự động gửi lệnh.")
                with ui.row().classes("items-end gap-3 flex-wrap"):
                    refs["extra_cash"] = ui.number("Tiền mới VND", value=0, min=0, step=1_000_000).classes("w-56")
                    refs["include_cash"] = ui.checkbox("Dùng cả tiền planner hiện có", value=False)
                    refs["plan_lot"] = ui.number("Lot", value=100, min=1).classes("w-28")
                    refs["plan_fee"] = ui.number("Phí mua bps", value=15, min=0).classes("w-36")
                    refs["plan_slippage"] = ui.number("Slippage bps", value=10, min=0).classes("w-36")
                    refs["plan_button"] = ui.button("PHÂN TÍCH TIỀN MỚI", icon="calculate").props("unelevated no-caps color=accent")
                refs["plan_summary"] = ui.label("Nhập số tiền mới rồi chạy planner.").classes("text-body2 text-grey-7 mt-2")
                refs["plan_table"] = ui.table(
                    columns=_columns((
                        ("rank", "Hạng"), ("symbol", "Mã"), ("current_quantity", "Đang có"),
                        ("current_weight", "Hiện tại"), ("target_weight", "Target"),
                        ("buy_quantity", "Mua thêm"), ("cost", "Chi phí"),
                        ("post_weight", "Sau mua"), ("status", "Trạng thái"),
                    )), rows=[], row_key="symbol", pagination=15,
                ).classes("w-full compact-table").props("flat bordered dense")

            with ui.row().classes("w-full gap-4 flex-wrap").props("id=signals"):
                with ui.card().classes("surface grow min-w-[620px] p-4"):
                    section_title("Watchlist có lý do", "Không diễn giải score như xác suất tăng giá.")
                    refs["watchlist_table"] = ui.table(
                        columns=_columns((("rank", "Hạng"), ("symbol", "Mã"), ("target", "Target"), ("score", "Score"), ("reason", "Lý do"))),
                        rows=[], row_key="symbol", pagination=10,
                    ).classes("w-full compact-table").props("flat bordered dense")
                with ui.card().classes("surface grow min-w-[400px] p-4"):
                    section_title("Bức tranh model")
                    refs["model_explain"] = ui.label("—").classes("text-body1")
                    refs["model_detail"] = ui.label("—").classes("text-body2 text-grey-7")
                    refs["market_detail"] = ui.label("—").classes("text-body2 text-grey-7 mt-3")

            with ui.card().classes("surface w-full p-4").props("id=paper"):
                with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
                    with ui.column().classes("gap-0"):
                        section_title("Paper trading", "Luôn hiển thị trạng thái; snapshot trong phiên không tạo fill.")
                    refs["paper_state"] = ui.badge("Chưa có sổ", color="grey").props("outline")
                with ui.row().classes("w-full gap-3 flex-wrap mt-2"):
                    metric("NAV", "paper_nav_detail")
                    metric("Lợi nhuận", "paper_return")
                    metric("Max drawdown", "paper_drawdown")
                    metric("Fill", "paper_fills")
                    metric("Lệnh chờ", "paper_pending")
                refs["paper_message"] = ui.label("Chưa có paper snapshot.").classes("text-body2 text-grey-7")
                refs["paper_chart"] = ui.echart({
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "scale": True},
                    "series": [{"type": "line", "data": [], "showSymbol": False, "smooth": True}],
                }).classes("w-full h-72")
                refs["paper_positions"] = ui.table(columns=[], rows=[], pagination=10).classes("w-full compact-table").props("flat bordered dense")

            with ui.card().classes("surface w-full p-4").props("id=research"):
                section_title("Kiểm định và bằng chứng", "Mặc định thu gọn; chỉ mở khi cần kiểm tra sâu.")
                with ui.expansion("So sánh model OOS", icon="science").classes("w-full"):
                    refs["model_chart"] = ui.echart({
                        "tooltip": {"trigger": "axis"},
                        "legend": {"data": ["Momentum", "Robust", "LightGBM"]},
                        "xAxis": {"type": "category", "data": ["Rank IC", "Precision@10", "Top10 rel", "Turnover"]},
                        "yAxis": {"type": "value", "scale": True},
                        "series": [
                            {"type": "bar", "name": "Momentum", "data": [0, 0, 0, 0]},
                            {"type": "bar", "name": "Robust", "data": [0, 0, 0, 0]},
                            {"type": "bar", "name": "LightGBM", "data": [0, 0, 0, 0]},
                        ],
                    }).classes("w-full h-80")
                    refs["research_note"] = ui.label("—").classes("text-body2 text-grey-7")

            with ui.card().classes("surface w-full p-4").props("id=operations"):
                section_title("Vận hành", "Log và tham số nâng cao không chiếm không gian ở màn hình chính.")
                with ui.expansion("Cấu hình chạy", icon="tune").classes("w-full"):
                    with ui.row().classes("gap-3 flex-wrap"):
                        refs["target_date"] = ui.input("Ngày mục tiêu; trống = hôm nay").classes("w-56")
                        refs["secondary"] = ui.select({"vci": "VCI", "kbs": "KBS"}, value="vci", label="Nguồn đối chiếu").classes("w-44")
                        refs["sample_size"] = ui.number("Mẫu đối chiếu", value=20, min=0, step=1).classes("w-40")
                        refs["paper_capital"] = ui.number("Vốn paper", value=1_000_000_000, min=1_000_000, step=1_000_000).classes("w-52")
                        refs["buy_fee"] = ui.number("Phí mua bps", value=15, min=0).classes("w-36")
                        refs["sell_fee"] = ui.number("Phí bán bps", value=15, min=0).classes("w-36")
                        refs["sell_tax"] = ui.number("Thuế bán bps", value=100, min=0).classes("w-36")
                        refs["slippage"] = ui.number("Slippage bps", value=10, min=0).classes("w-36")
                        refs["lot"] = ui.number("Lot", value=100, min=1).classes("w-28")
                with ui.expansion("Log job", icon="terminal").classes("w-full"):
                    refs["job_log"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono")

    def set_action(index: int, payload: Mapping[str, object] | None) -> None:
        card = refs[f"action_card_{index}"]
        for cls in ("action-positive", "action-warning", "action-negative", "action-info"):
            card.classes(remove=cls)
        if not payload:
            refs[f"action_title_{index}"].set_text("Chưa có kết luận")
            refs[f"action_detail_{index}"].set_text("Cập nhật dữ liệu và đồng bộ danh mục.")
            card.classes(add="action-info")
            return
        severity = str(payload.get("severity") or "info")
        card.classes(add=f"action-{severity}")
        refs[f"action_title_{index}"].set_text(str(payload.get("title") or "—"))
        refs[f"action_detail_{index}"].set_text(str(payload.get("detail") or "—"))

    def load_context() -> dict[str, object]:
        run, paths, manifest, quality, model, predictions, allocation = _latest_bundle(config)
        portfolio_snapshot = _latest_portfolio_snapshot(config.data_root)
        portfolio_summary = _json(portfolio_snapshot / "portfolio_summary.json") if portfolio_snapshot else {}
        portfolio_rows = _csv(portfolio_snapshot / "portfolio_analysis.csv", limit=1000) if portfolio_snapshot else []
        paper_snapshot = latest_paper_snapshot(config.data_root)
        paper_metrics = _json(paper_snapshot / "metrics.json") if paper_snapshot else {}
        brief = build_decision_brief(
            manifest=manifest,
            quality=quality,
            model=model,
            predictions=predictions,
            allocation=allocation,
            portfolio_summary=portfolio_summary,
            portfolio_analysis=portfolio_rows,
            paper_metrics=paper_metrics,
            paper_status_text=_paper_status(paper_snapshot),
        )
        return {
            "run": run, "paths": paths, "manifest": manifest, "quality": quality,
            "model": model, "predictions": predictions, "allocation": allocation,
            "portfolio_snapshot": portfolio_snapshot, "portfolio_summary": portfolio_summary,
            "portfolio_rows": portfolio_rows, "paper_snapshot": paper_snapshot,
            "paper_metrics": paper_metrics, "brief": brief,
        }

    def refresh_all() -> None:
        try:
            context = load_context()
            manifest = context["manifest"]
            model = context["model"]
            brief = context["brief"]
            portfolio_summary = context["portfolio_summary"]
            data_state = brief["data"]
            model_state = brief["model"]
            refs["market_regime"].set_text(str(brief.get("regime") or "—"))
            refs["market_regime_note"].set_text(f"Ngân sách cổ phiếu {_pct(brief.get('capital_budget_pct'), already_percent=True)}")
            refs["data_grade"].set_text(str(data_state.get("label") or "—"))
            refs["data_grade_note"].set_text(str(data_state.get("detail") or "—"))
            refs["model_grade"].set_text(str(model_state.get("label") or "—"))
            refs["model_grade_note"].set_text(str(model_state.get("detail") or "—"))
            refs["portfolio_nav"].set_text(_vnd(portfolio_summary.get("net_liquidation_value_vnd")))
            refs["portfolio_nav_note"].set_text(str(portfolio_summary.get("masked_account") or "Chưa đồng bộ"))
            refs["planner_cash"].set_text(_vnd(portfolio_summary.get("planner_cash_vnd", portfolio_summary.get("safe_planner_cash_vnd"))))
            refs["planner_cash_note"].set_text(str(portfolio_summary.get("cash_semantics_status") or "Chưa xác minh cash semantics"))
            paper = brief["paper"]
            refs["paper_nav"].set_text(_vnd(paper.get("nav_vnd")))
            refs["paper_nav_note"].set_text(str(paper.get("label") or "—"))
            refs["command_summary"].set_text(
                f"{data_state.get('label')} · {model_state.get('label')} · Regime {brief.get('regime')} · dữ liệu {manifest.get('session_date') or model.get('signal_date') or '—'}"
            )
            for index in range(3):
                actions = brief.get("actions") if isinstance(brief.get("actions"), list) else []
                set_action(index, actions[index] if index < len(actions) and isinstance(actions[index], Mapping) else None)

            position_view = _present_positions(brief.get("positions", []))
            refs["portfolio_table"].rows = position_view
            refs["portfolio_table"].update()
            refs["portfolio_empty"].set_visibility(not bool(position_view))
            snapshot = context.get("portfolio_snapshot")
            refs["portfolio_asof"].set_text(
                f"As of {portfolio_summary.get('as_of', '—')} · {portfolio_summary.get('masked_account', '—')}"
                if snapshot else "Chưa đồng bộ"
            )
            warnings = portfolio_summary.get("warnings") if isinstance(portfolio_summary.get("warnings"), list) else []
            refs["portfolio_diagnostics"].set_text(
                f"Sức mua broker: {_vnd(portfolio_summary.get('broker_buying_power_vnd', portfolio_summary.get('available_cash_vnd')))} · "
                f"Total cash: {_vnd(portfolio_summary.get('total_cash_vnd'))} · "
                f"Withdrawable: {_vnd(portfolio_summary.get('withdrawable_cash_vnd'))} · "
                f"Largest NAV weight: {_pct(portfolio_summary.get('largest_position_nav_weight', portfolio_summary.get('largest_position_weight')))} · "
                f"Cảnh báo: {'; '.join(str(item) for item in warnings) or 'không có'}"
            )

            refs["watchlist_table"].rows = _present_watchlist(brief.get("watchlist", []))
            refs["watchlist_table"].update()
            refs["model_explain"].set_text(str(model_state.get("label") or "—"))
            refs["model_detail"].set_text(str(model_state.get("detail") or "—"))
            refs["market_detail"].set_text(
                f"Breadth MA250 {_pct(model.get('breadth_above_ma250'))} · Benchmark bars {model.get('benchmark_bar_count', '—')} · Research eligible={model.get('research_eligible', False)}"
            )

            paper_snapshot = context.get("paper_snapshot")
            paper_metrics = context.get("paper_metrics")
            refs["paper_state"].set_text(str(paper.get("label") or "—"))
            refs["paper_state"].props(f"color={'positive' if paper.get('state') == 'ACTIVE' else 'warning' if paper.get('state') == 'PENDING' else 'grey'}")
            refs["paper_nav_detail"].set_text(_vnd(paper.get("nav_vnd")))
            refs["paper_return"].set_text(_pct(paper_metrics.get("total_return") if isinstance(paper_metrics, Mapping) else 0))
            refs["paper_drawdown"].set_text(_pct(paper_metrics.get("max_drawdown") if isinstance(paper_metrics, Mapping) else 0))
            refs["paper_fills"].set_text(str(paper.get("fills") or 0))
            refs["paper_pending"].set_text(str(paper.get("pending") or 0))
            refs["paper_message"].set_text(str(paper.get("detail") or "—"))
            nav_rows = load_paper_nav(paper_snapshot) if paper_snapshot else []
            refs["paper_chart"].options["xAxis"]["data"] = [row.get("ngay") or row.get("date") for row in nav_rows]
            refs["paper_chart"].options["series"][0]["data"] = [float(row.get("nav_vnd") or row.get("nav") or 0) for row in nav_rows]
            refs["paper_chart"].update()
            paper_positions = load_paper_positions(paper_snapshot) if paper_snapshot else []
            refs["paper_positions"].columns = base._columns(paper_positions, ("ma", "symbol", "so_luong", "quantity", "gia_von", "market_value_vnd"))
            refs["paper_positions"].rows = paper_positions
            refs["paper_positions"].update()

            metrics: list[list[float]] = []
            for name in ("momentum_validation", "robust_reference_validation", "lightgbm_validation"):
                raw = model.get(name) if isinstance(model.get(name), Mapping) else {}
                metrics.append([float(raw.get(key, 0) or 0) for key in ("mean_rank_ic", "precision_at_k", "top_k_relative_return", "mean_set_turnover")])
            for index, values in enumerate(metrics):
                refs["model_chart"].options["series"][index]["data"] = values
            refs["model_chart"].update()
            refs["research_note"].set_text(
                f"Champion {model.get('champion_model', '—')} · Ranking {model.get('ranking_model', model.get('reference_model', '—'))} · Robust validation {model.get('robust_validation_status', '—')}"
            )
            status = str(manifest.get("data_status") or "FINAL")
            refs["header_data"].set_text(status)
            refs["header_data"].props(f"color={'positive' if status == 'FINAL' else 'warning'}")
        except Exception as exc:
            refs["command_summary"].set_text(f"Chưa đọc được kết quả: {type(exc).__name__}: {exc}")
            for index in range(3):
                set_action(index, None)

    async def connect_dnse() -> None:
        refs["connect_button"].set_enabled(False)
        try:
            def work() -> list[dict[str, str]]:
                client = DnseReadOnlyClient.from_env()
                try:
                    return list_masked_accounts(client)
                finally:
                    client.close()
            accounts = await asyncio.to_thread(work)
            token_map = {f"account-{index + 1}": item["account_no"] for index, item in enumerate(accounts)}
            state["accounts"] = token_map
            options = {
                token: f"{accounts[index]['masked_account']} · {accounts[index]['account_type']}"
                for index, token in enumerate(token_map)
            }
            refs["account_select"].options = options
            refs["account_select"].value = next(iter(options), None)
            refs["account_select"].update()
            refs["header_connection"].set_text("DNSE đã xác thực")
            refs["header_connection"].props("color=positive")
            refs["connection_note"].set_text(f"Đã tải {len(accounts)} tiểu khoản; số thật chỉ giữ trong memory local.")
            ui.notify("Kết nối DNSE OpenAPI thành công.", type="positive")
        except Exception as exc:
            refs["header_connection"].set_text("DNSE lỗi xác thực")
            refs["header_connection"].props("color=negative")
            refs["connection_note"].set_text(f"{type(exc).__name__}: {exc}")
            ui.notify("Không xác thực được DNSE OpenAPI.", type="negative", timeout=8000)
        finally:
            refs["connect_button"].set_enabled(True)

    async def sync_dnse(*, silent: bool = False) -> None:
        if state.get("syncing"):
            return
        state["syncing"] = True
        refs["sync_button"].set_enabled(False)
        refs["sync_button_side"].set_enabled(False)
        token = str(refs["account_select"].value or "")
        account_map = state.get("accounts") if isinstance(state.get("accounts"), Mapping) else {}
        account_no = account_map.get(token)
        output = config.data_root / "dnse-portfolio-live" / "snapshots" / datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
        try:
            result = await asyncio.to_thread(
                sync_portfolio,
                data_root=config.data_root,
                output_dir=output,
                account_no=str(account_no) if account_no else None,
                sync_local_planner=True,
                include_market_context=True,
            )
            refs["header_connection"].set_text(f"DNSE {result['masked_account']}")
            refs["header_connection"].props("color=positive")
            refresh_all()
            if not silent:
                ui.notify("Đã đồng bộ danh mục và cash semantics an toàn.", type="positive")
        except Exception as exc:
            refs["connection_note"].set_text(f"Đồng bộ lỗi: {type(exc).__name__}: {exc}")
            if not silent:
                ui.notify("Đồng bộ danh mục thất bại; không có lệnh giao dịch nào được gửi.", type="negative", timeout=9000)
        finally:
            state["syncing"] = False
            refs["sync_button"].set_enabled(True)
            refs["sync_button_side"].set_enabled(True)

    async def launch(job_id: str, step: PipelineStep) -> None:
        await asyncio.to_thread(execute_job, store=jobs, job_id=job_id, config=config, steps=(step,))

    async def start_run() -> None:
        try:
            target_text = str(refs["target_date"].value or "").strip()
            target = date.fromisoformat(target_text) if target_text else None
            run_id = datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
            output = config.data_root / f"anytime-web-{run_id}"
            command = [
                sys.executable, "-m", "he_thong_dinh_luong.anytime_pipeline",
                "--repo-root", str(config.repo_root),
                "--data-root", str(config.data_root),
                "--output-dir", str(output),
                "--mode", str(refs["run_mode"].value),
                "--secondary-source", str(refs["secondary"].value),
                "--crosscheck-sample-size", str(int(refs["sample_size"].value or 20)),
                "--initial-capital-vnd", str(int(refs["paper_capital"].value or 1_000_000_000)),
                "--buy-fee-bps", str(float(refs["buy_fee"].value or 0)),
                "--sell-fee-bps", str(float(refs["sell_fee"].value or 0)),
                "--sell-tax-bps", str(float(refs["sell_tax"].value or 0)),
                "--slippage-bps", str(float(refs["slippage"].value or 0)),
                "--lot-size", str(int(refs["lot"].value or 100)),
            ]
            if target is not None:
                command.extend(("--target-date", target.isoformat()))
            log_path = config.logs_dir / f"{output.name}.log"
            job_id = jobs.create_job(
                kind="terminal_refresh",
                output_dir=output,
                log_path=log_path,
                parameters={"mode": refs["run_mode"].value, "target_date": target.isoformat() if target else None},
            )
            state["auto_sync_job"] = job_id
            asyncio.create_task(launch(job_id, PipelineStep("update_market_and_models", tuple(command))))
            ui.notify("Đã bắt đầu cập nhật; kết quả sẽ tự hiện trên màn hình này.", type="positive")
        except Exception as exc:
            ui.notify(f"Không thể chạy: {type(exc).__name__}: {exc}", type="negative", timeout=8000)

    def build_plan() -> None:
        try:
            run, paths, _, _, model, predictions, allocation = _latest_bundle(config)
            price_rows = base._csv(paths["publication"], limit=10_000_000)
            prices, price_day = latest_price_map(price_rows)
            request = PlanRequest(
                extra_cash_vnd=int(refs["extra_cash"].value or 0),
                current_cash_vnd=portfolio.get_current_cash(),
                include_current_cash=bool(refs["include_cash"].value),
                lot_size=int(refs["plan_lot"].value or 100),
                buy_fee_bps=Decimal(str(refs["plan_fee"].value or 0)),
                slippage_bps=Decimal(str(refs["plan_slippage"].value or 0)),
            )
            plan = build_incremental_plan(
                holdings=portfolio.list_holdings(),
                price_vnd=prices,
                allocation_rows=allocation,
                predictions=predictions,
                model=model,
                request=request,
            )
            portfolio.record_plan(plan)
            rows = []
            for raw in plan.get("rows", []):
                rows.append({
                    "rank": raw.get("rank"), "symbol": raw.get("symbol"),
                    "current_quantity": raw.get("current_quantity"),
                    "current_weight": _pct(raw.get("current_weight_pct"), already_percent=True),
                    "target_weight": _pct(raw.get("target_weight_pct"), already_percent=True),
                    "buy_quantity": raw.get("recommended_buy_quantity"),
                    "cost": _vnd(raw.get("estimated_all_in_cost_vnd")),
                    "post_weight": _pct(raw.get("post_weight_pct"), already_percent=True),
                    "status": raw.get("status"),
                })
            refs["plan_table"].rows = rows
            refs["plan_table"].update()
            refs["plan_summary"].set_text(
                f"Giá ngày {price_day} · dự kiến dùng {_vnd(plan.get('estimated_spend_vnd'))} · còn {_vnd(plan.get('remaining_available_cash_vnd'))} · nguồn {run.name}."
            )
            ui.notify("Đã tạo kế hoạch tiền mới; không có lệnh thật được gửi.", type="positive")
        except Exception as exc:
            ui.notify(f"Không thể chia tiền: {type(exc).__name__}: {exc}", type="negative", timeout=9000)

    def active_tick() -> None:
        refs["header_clock"].set_text(datetime.now(VN_TZ).strftime("%H:%M:%S"))
        active = jobs.active()
        refs["run_button"].set_enabled(active is None)
        refs["progress"].set_visibility(active is not None)
        if active:
            refs["job_status"].set_text(f"{active['stage']} · job {active['id'][:8]}")
            refs["job_log"].value = read_log_tail(Path(str(active["log_path"])), 400)
            refs["job_log"].update()
            state["last_job"] = None
            return
        recent = jobs.recent(1)
        latest = recent[0] if recent else None
        if latest:
            refs["job_status"].set_text(f"Job gần nhất: {latest['status']} · exit={latest['return_code']}")
            refs["job_log"].value = read_log_tail(Path(str(latest["log_path"])), 400)
            refs["job_log"].update()
            if latest["status"] in {"SUCCESS", "FAILED"} and state.get("last_job") != latest["id"]:
                state["last_job"] = latest["id"]
                refresh_all()
                if latest["status"] == "SUCCESS":
                    ui.notify("Phân tích hoàn tất; đang đồng bộ danh mục DNSE.", type="positive")
                    if state.get("auto_sync_job") == latest["id"] and os.environ.get("DNSE_API_KEY") and os.environ.get("DNSE_API_SECRET"):
                        state["auto_sync_job"] = None
                        asyncio.create_task(sync_dnse(silent=True))
                else:
                    ui.notify(f"Job lỗi: {latest['error']}", type="negative", timeout=9000)

    refs["connect_button"].on("click", connect_dnse)
    refs["sync_button"].on("click", sync_dnse)
    refs["sync_button_side"].on("click", sync_dnse)
    refs["run_button"].on("click", start_run)
    refs["plan_button"].on("click", build_plan)
    refresh_all()
    ui.timer(1.0, active_tick)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = LocalWebConfig(
        repo_root=args.repo_root.resolve(),
        data_root=args.data_root.resolve(),
        host=args.host,
        port=args.port,
    )
    if config.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("WEB_LOCALHOST_ONLY")
    if not (config.repo_root / "src" / "he_thong_dinh_luong").is_dir():
        raise ValueError("REPO_ROOT_INVALID")
    config.data_root.mkdir(parents=True, exist_ok=True)
    jobs = JobStore(config.jobs_db)
    jobs.interrupt_stale_jobs()
    portfolio = PortfolioStore(config.ui_state_dir / "portfolio.sqlite3")
    try:
        import nicegui
        from nicegui import app, ui
    except ImportError as exc:
        raise RuntimeError(f"NICEGUI_NOT_INSTALLED:{NICEGUI_VERSION}") from exc
    version = getattr(nicegui, "__version__", "")
    if version and version != NICEGUI_VERSION:
        raise RuntimeError(f"NICEGUI_VERSION_MISMATCH:{version}!={NICEGUI_VERSION}")

    @app.get("/healthz")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app": "vn-quant-local-terminal",
            "version": "5",
            "nicegui_version": NICEGUI_VERSION,
            "localhost_only": True,
            "dnse_auth": "api_key_secret_only",
            "dnse_password_login": False,
            "trading_enabled": False,
        }

    @ui.page("/")
    def index() -> None:
        build_app(ui, config, jobs, portfolio)

    ui.run(
        host=config.host,
        port=config.port,
        title=APP_TITLE,
        reload=False,
        show=args.show_browser,
        favicon="📈",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
