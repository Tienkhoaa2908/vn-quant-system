"""Giao dien web local cho van hanh EOD, model, allocation va paper trading.

Chay bang NiceGUI tren 127.0.0.1. Module chi import NiceGUI trong ``main`` de
bo test nen khong can cai dependency UI.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Sequence

from .web_local_core import (
    DailyPipelineRequest,
    JobStore,
    LocalWebConfig,
    PaperScenarioRequest,
    artifact_paths,
    create_daily_job,
    create_scenario_job,
    discover_eod_runs,
    execute_job,
    latest_paper_snapshot,
    latest_publication_dir,
    latest_successful_eod,
    load_latest_allocation,
    load_latest_predictions,
    load_latest_prices,
    load_model_comparison,
    load_overview,
    load_paper_nav,
    load_paper_positions,
    load_quality_report,
    read_log_tail,
)

NICEGUI_VERSION = "3.14.0"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.giao_dien_web")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    return parser


def _number(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _percent(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def _vnd(value: object) -> str:
    try:
        return f"{float(value):,.0f} ₫"
    except (TypeError, ValueError):
        return "—"


def _columns(rows: list[dict[str, str]], preferred: Sequence[str] = ()) -> list[dict[str, str]]:
    if not rows:
        return []
    names = list(rows[0])
    ordered = [name for name in preferred if name in names]
    ordered.extend(name for name in names if name not in ordered)
    return [
        {"name": name, "label": name, "field": name, "sortable": True, "align": "left"}
        for name in ordered
    ]


def _open_explorer(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"PATH_NOT_FOUND:{path}")
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _metric_values(model: Mapping[str, object], name: str) -> dict[str, float]:
    raw = model.get(name, {})
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, float] = {}
    for key in ("mean_rank_ic", "precision_at_k", "top_k_relative_return", "mean_set_turnover"):
        try:
            result[key] = float(raw.get(key, 0))
        except (TypeError, ValueError):
            result[key] = 0.0
    return result


def build_app(ui: Any, config: LocalWebConfig, store: JobStore) -> None:
    """Lap rap toan bo UI. ``ui`` duoc truyen vao de module van import duoc khi thieu NiceGUI."""
    ui.colors(primary="#1f4e78", secondary="#455a64", accent="#00897b")
    ui.add_css("""
        body { background: #f4f6f8; }
        .metric-card { min-width: 190px; flex: 1 1 190px; }
        .metric-value { font-size: 1.55rem; font-weight: 700; }
        .section-title { font-size: 1.2rem; font-weight: 700; margin-top: 0.5rem; }
        .mono-box textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    """)

    state: dict[str, object] = {"last_terminal_job": None}

    with ui.header().classes("items-center justify-between bg-primary text-white"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("query_stats", size="32px")
            with ui.column().classes("gap-0"):
                ui.label("VN Quant Local Console").classes("text-h6")
                ui.label("DNSE EOD · ranking · allocation · backtest · paper").classes("text-caption")
        header_status = ui.label("Đang đọc trạng thái...").classes("text-caption")

    tabs = ui.tabs().classes("w-full bg-white shadow-sm")
    with tabs:
        tab_overview = ui.tab("Tổng quan", icon="dashboard")
        tab_run = ui.tab("Chạy một nút", icon="play_circle")
        tab_data = ui.tab("Dữ liệu", icon="storage")
        tab_prediction = ui.tab("Dự đoán & vốn", icon="leaderboard")
        tab_backtest = ui.tab("Kiểm định", icon="science")
        tab_paper = ui.tab("Paper trading", icon="account_balance_wallet")
        tab_jobs = ui.tab("Nhật ký", icon="terminal")

    # Mutable references used by refresh callbacks.
    refs: dict[str, Any] = {}

    def metric_card(title: str, key: str, note: str = "") -> None:
        with ui.card().classes("metric-card"):
            ui.label(title).classes("text-caption text-grey-7")
            refs[key] = ui.label("—").classes("metric-value")
            if note:
                ui.label(note).classes("text-caption text-grey-6")

    with ui.tab_panels(tabs, value=tab_overview).classes("w-full bg-transparent"):
        with ui.tab_panel(tab_overview):
            ui.label("Trạng thái hệ thống").classes("section-title")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric_card("Phiên dữ liệu mới nhất", "session_date")
                metric_card("Coverage DNSE", "primary_coverage")
                metric_card("Champion", "champion_model")
                metric_card("Market regime", "market_regime")
                metric_card("Ngân sách vốn", "capital_budget")
                metric_card("NAV paper", "paper_nav")
            with ui.row().classes("w-full gap-3 items-stretch"):
                with ui.card().classes("grow"):
                    ui.label("Top ranking mới nhất").classes("section-title")
                    refs["overview_prediction_table"] = ui.table(
                        columns=[], rows=[], row_key="symbol", pagination=10
                    ).classes("w-full")
                with ui.card().classes("grow"):
                    ui.label("NAV paper").classes("section-title")
                    refs["overview_nav_chart"] = ui.echart({
                        "xAxis": {"type": "category", "data": []},
                        "yAxis": {"type": "value", "scale": True},
                        "tooltip": {"trigger": "axis"},
                        "series": [{"type": "line", "data": [], "showSymbol": False}],
                    }).classes("w-full h-80")
            refs["overview_note"] = ui.label().classes("text-caption text-grey-7")

        with ui.tab_panel(tab_run):
            ui.label("Cập nhật toàn hệ thống").classes("section-title")
            ui.label(
                "Một nút sẽ lấy các phiên còn thiếu từ DNSE, kiểm tra nguồn phụ, "
                "tạo feature, chạy champion–challenger, phân bổ vốn và cập nhật sổ paper."
            ).classes("text-body2 text-grey-8")
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full gap-4 items-end flex-wrap"):
                    refs["target_date"] = ui.input(
                        "Ngày mục tiêu (YYYY-MM-DD, để trống = hôm nay)", value=""
                    ).classes("w-72")
                    refs["secondary_source"] = ui.select(
                        {"vci": "VCI", "kbs": "KBS"}, value="vci", label="Nguồn đối chiếu"
                    ).classes("w-48")
                    refs["sample_size"] = ui.number(
                        "Số mã kiểm tra mẫu", value=20, min=0, step=1
                    ).classes("w-48")
                    refs["run_button"] = ui.button(
                        "LẤY DATA + CHẠY MODEL + PAPER",
                        icon="play_arrow",
                    ).props("unelevated size=lg")
                with ui.expansion("Chi phí và vốn paper", icon="tune").classes("w-full"):
                    with ui.row().classes("gap-4 flex-wrap"):
                        refs["initial_capital"] = ui.number(
                            "Vốn giả định (VND)", value=1_000_000_000, min=1_000_000, step=1_000_000
                        )
                        refs["buy_fee"] = ui.number("Phí mua (bps)", value=15, min=0, step=1)
                        refs["sell_fee"] = ui.number("Phí bán (bps)", value=15, min=0, step=1)
                        refs["sell_tax"] = ui.number("Thuế bán (bps)", value=100, min=0, step=1)
                        refs["slippage"] = ui.number("Slippage (bps)", value=10, min=0, step=1)
                        refs["lot_size"] = ui.number("Lot size", value=100, min=1, step=1)
                refs["run_status"] = ui.label("Chưa có job đang chạy.").classes("text-body1")
                refs["run_log"] = ui.textarea(
                    label="Log sống", value=""
                ).props("readonly autogrow").classes("w-full mono-box")

        with ui.tab_panel(tab_data):
            ui.label("Khám phá dữ liệu model đang dùng").classes("section-title")
            with ui.row().classes("items-end gap-3"):
                refs["data_symbol"] = ui.input("Mã cổ phiếu", value="HPG").classes("w-48")
                refs["data_limit"] = ui.number("Số dòng", value=120, min=10, max=2000, step=10)
                refs["data_refresh_button"] = ui.button("Đọc dữ liệu", icon="search")
                refs["open_data_button"] = ui.button("Mở thư mục EOD", icon="folder_open").props("outline")
            refs["data_table"] = ui.table(
                columns=[], rows=[], row_key="ngay", pagination=25
            ).classes("w-full")
            with ui.card().classes("w-full"):
                ui.label("Chất lượng dữ liệu").classes("section-title")
                refs["quality_text"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono-box")

        with ui.tab_panel(tab_prediction):
            ui.label("Ranking và phân bổ vốn").classes("section-title")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric_card("Champion model", "pred_champion")
                metric_card("Regime", "pred_regime")
                metric_card("Vốn được phép", "pred_budget")
                metric_card("Số ứng viên", "pred_candidates")
            ui.label("Toàn bộ ranking").classes("section-title")
            refs["prediction_table"] = ui.table(
                columns=[], rows=[], row_key="symbol", pagination=25
            ).classes("w-full")
            ui.label("Danh mục mục tiêu").classes("section-title")
            refs["allocation_table"] = ui.table(
                columns=[], rows=[], row_key="symbol", pagination=20
            ).classes("w-full")

        with ui.tab_panel(tab_backtest):
            ui.label("Kiểm định model và replay paper lịch sử").classes("section-title")
            ui.label(
                "Biểu đồ bên dưới so sánh validation OOS. Replay scenario chỉ dùng các tín hiệu "
                "OOS đã được ghi nhận; không tự dựng tín hiệu cho những ngày chưa từng chạy."
            ).classes("text-body2 text-grey-8")
            refs["model_chart"] = ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["Momentum", "LightGBM"]},
                "xAxis": {"type": "category", "data": ["Rank IC", "Precision@10", "Top10 rel", "Turnover"]},
                "yAxis": {"type": "value", "scale": True},
                "series": [
                    {"type": "bar", "name": "Momentum", "data": [0, 0, 0, 0]},
                    {"type": "bar", "name": "LightGBM", "data": [0, 0, 0, 0]},
                ],
            }).classes("w-full h-96")
            with ui.card().classes("w-full"):
                ui.label("Chạy lại scenario paper đã ghi nhận").classes("section-title")
                with ui.row().classes("gap-4 items-end flex-wrap"):
                    refs["scenario_capital"] = ui.number(
                        "Vốn (VND)", value=1_000_000_000, min=1_000_000, step=1_000_000
                    )
                    refs["scenario_buy_fee"] = ui.number("Phí mua", value=15, min=0)
                    refs["scenario_sell_fee"] = ui.number("Phí bán", value=15, min=0)
                    refs["scenario_tax"] = ui.number("Thuế bán", value=100, min=0)
                    refs["scenario_slippage"] = ui.number("Slippage", value=10, min=0)
                    refs["scenario_lot"] = ui.number("Lot", value=100, min=1, step=1)
                    refs["scenario_button"] = ui.button("Chạy scenario", icon="replay")
                refs["scenario_status"] = ui.label("Chưa chạy scenario.")

        with ui.tab_panel(tab_paper):
            ui.label("Paper trading OOS sống").classes("section-title")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric_card("Trạng thái", "paper_status")
                metric_card("NAV mới nhất", "paper_nav_detail")
                metric_card("Lợi nhuận", "paper_return")
                metric_card("Max drawdown", "paper_drawdown")
                metric_card("Số fill", "paper_fill")
                metric_card("Lệnh chờ", "paper_pending")
            refs["paper_nav_chart"] = ui.echart({
                "xAxis": {"type": "category", "data": []},
                "yAxis": {"type": "value", "scale": True},
                "tooltip": {"trigger": "axis"},
                "dataZoom": [{"type": "inside"}, {"type": "slider"}],
                "series": [{"type": "line", "data": [], "showSymbol": False}],
            }).classes("w-full h-96")
            ui.label("Vị thế gần nhất").classes("section-title")
            refs["positions_table"] = ui.table(
                columns=[], rows=[], row_key="ma", pagination=25
            ).classes("w-full")
            refs["open_paper_button"] = ui.button("Mở thư mục paper", icon="folder_open").props("outline")

        with ui.tab_panel(tab_jobs):
            ui.label("Job, log và cấu hình local").classes("section-title")
            with ui.row().classes("gap-3"):
                refs["refresh_jobs_button"] = ui.button("Làm mới", icon="refresh")
                refs["open_logs_button"] = ui.button("Mở thư mục log", icon="folder_open").props("outline")
            refs["jobs_table"] = ui.table(
                columns=[
                    {"name": "created_at", "label": "Thời gian", "field": "created_at", "sortable": True},
                    {"name": "kind", "label": "Loại", "field": "kind"},
                    {"name": "status", "label": "Trạng thái", "field": "status"},
                    {"name": "stage", "label": "Bước", "field": "stage"},
                    {"name": "return_code", "label": "Exit", "field": "return_code"},
                    {"name": "output_dir", "label": "Output", "field": "output_dir"},
                ],
                rows=[], row_key="id", pagination=20, selection="single",
            ).classes("w-full")
            refs["job_log"] = ui.textarea(label="Log job được chọn", value="").props("readonly autogrow").classes("w-full mono-box")
            with ui.card().classes("w-full"):
                ui.label("Cấu hình").classes("section-title")
                refs["settings_text"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono-box")

    async def launch_job(job_id: str, steps: Sequence[object]) -> None:
        await asyncio.to_thread(
            execute_job,
            store=store,
            job_id=job_id,
            config=config,
            steps=steps,
        )

    async def start_daily() -> None:
        try:
            target_text = str(refs["target_date"].value or "").strip()
            target = date.fromisoformat(target_text) if target_text else None
            request = DailyPipelineRequest(
                target_date=target,
                secondary_source=str(refs["secondary_source"].value),
                crosscheck_sample_size=int(refs["sample_size"].value),
                initial_capital_vnd=int(refs["initial_capital"].value),
                buy_fee_bps=float(refs["buy_fee"].value),
                sell_fee_bps=float(refs["sell_fee"].value),
                sell_tax_bps=float(refs["sell_tax"].value),
                slippage_bps=float(refs["slippage"].value),
                lot_size=int(refs["lot_size"].value),
            )
            job_id, output_dir, steps = create_daily_job(store, config, request)
            refs["run_status"].set_text(f"Đã xếp job {job_id[:8]} → {output_dir}")
            ui.notify("Đã bắt đầu pipeline. Không đóng cửa sổ console.", type="positive")
            asyncio.create_task(launch_job(job_id, steps))
        except Exception as exc:
            ui.notify(f"Không thể chạy: {type(exc).__name__}: {exc}", type="negative", timeout=8000)

    async def start_scenario() -> None:
        try:
            publication = latest_publication_dir(config)
            if publication is None:
                raise ValueError("LATEST_PUBLICATION_NOT_FOUND")
            if latest_paper_snapshot(config.data_root) is None:
                raise ValueError("PAPER_SIGNAL_STORE_NOT_INITIALIZED")
            request = PaperScenarioRequest(
                initial_capital_vnd=int(refs["scenario_capital"].value),
                buy_fee_bps=float(refs["scenario_buy_fee"].value),
                sell_fee_bps=float(refs["scenario_sell_fee"].value),
                sell_tax_bps=float(refs["scenario_tax"].value),
                slippage_bps=float(refs["scenario_slippage"].value),
                lot_size=int(refs["scenario_lot"].value),
            )
            job_id, output_dir, steps = create_scenario_job(
                store, config, request, publication_dir=publication
            )
            refs["scenario_status"].set_text(f"Đang chạy {job_id[:8]} → {output_dir}")
            ui.notify("Đã bắt đầu replay scenario.", type="positive")
            asyncio.create_task(launch_job(job_id, steps))
        except Exception as exc:
            ui.notify(f"Không thể chạy scenario: {type(exc).__name__}: {exc}", type="negative", timeout=8000)

    def refresh_overview() -> None:
        overview = load_overview(config)
        refs["session_date"].set_text(str(overview.get("session_date") or "—"))
        refs["primary_coverage"].set_text(_percent(overview.get("primary_coverage")))
        refs["champion_model"].set_text(str(overview.get("champion_model") or "—"))
        refs["market_regime"].set_text(str(overview.get("market_regime") or "—"))
        budget = overview.get("capital_budget_pct")
        refs["capital_budget"].set_text(f"{_number(budget, 0)}%" if budget is not None else "—")
        refs["paper_nav"].set_text(_vnd(overview.get("paper_latest_nav_vnd")))
        header_status.set_text(
            f"DNSE: {'đã nạp credential' if overview['credential_loaded'] else 'chưa nạp'} · "
            f"Data: {overview.get('session_date') or 'chưa có'} · "
            f"Job: {(store.active() or {}).get('stage', 'rảnh')}"
        )
        predictions = load_latest_predictions(config, limit=10)
        preferred = ("champion_rank", "symbol", "champion_model", "momentum_12_1", "above_ma250", "technical_weight_pct")
        refs["overview_prediction_table"].columns = _columns(predictions, preferred)
        refs["overview_prediction_table"].rows = predictions
        refs["overview_prediction_table"].update()
        nav = load_paper_nav(config)
        x = [row.get("ngay", "") for row in nav]
        y = [_safe_chart_value(row.get("nav")) for row in nav]
        refs["overview_nav_chart"].options["xAxis"]["data"] = x
        refs["overview_nav_chart"].options["series"][0]["data"] = y
        refs["overview_nav_chart"].update()
        refs["overview_note"].set_text(
            "Research eligible: false. Dashboard phục vụ technical validation và paper trading."
        )

    def _safe_chart_value(value: object) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def refresh_data() -> None:
        symbol = str(refs["data_symbol"].value or "").strip().upper()
        limit = int(refs["data_limit"].value or 120)
        rows = load_latest_prices(config, symbol=symbol or None, limit=limit)
        refs["data_table"].columns = _columns(
            rows, ("ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong", "nguon", "phien_ban")
        )
        refs["data_table"].rows = rows
        refs["data_table"].update()
        quality = load_quality_report(config)
        compact = {
            key: quality.get(key)
            for key in (
                "status", "quality_tier", "session_date", "base_latest_date",
                "required_incremental_sessions", "symbol_count", "accepted_current_count",
                "primary_coverage", "crosscheck_sample_count", "secondary_match_ratio",
                "secondary_error_symbol_count", "benchmark_crosscheck",
            )
            if key in quality
        }
        refs["quality_text"].value = json.dumps(compact, ensure_ascii=False, indent=2)
        refs["quality_text"].update()

    def refresh_prediction() -> None:
        predictions = load_latest_predictions(config)
        allocation = load_latest_allocation(config)
        model = load_model_comparison(config)
        refs["prediction_table"].columns = _columns(
            predictions,
            ("champion_rank", "symbol", "selected_top_k", "technical_weight_pct", "momentum_12_1", "above_ma250", "relative_strength_120"),
        )
        refs["prediction_table"].rows = predictions
        refs["prediction_table"].update()
        refs["allocation_table"].columns = _columns(
            allocation, ("rank", "symbol", "target_weight_pct", "champion_model", "status")
        )
        refs["allocation_table"].rows = allocation
        refs["allocation_table"].update()
        refs["pred_champion"].set_text(str(model.get("champion_model") or "—"))
        refs["pred_regime"].set_text(str(model.get("market_regime") or "—"))
        budget = model.get("capital_budget_pct")
        refs["pred_budget"].set_text(f"{_number(budget, 0)}%" if budget is not None else "—")
        refs["pred_candidates"].set_text(str(model.get("forward_candidate_count") or "—"))
        momentum = _metric_values(model, "momentum_validation")
        lightgbm = _metric_values(model, "lightgbm_validation")
        metric_keys = ("mean_rank_ic", "precision_at_k", "top_k_relative_return", "mean_set_turnover")
        refs["model_chart"].options["series"][0]["data"] = [momentum.get(key, 0) for key in metric_keys]
        refs["model_chart"].options["series"][1]["data"] = [lightgbm.get(key, 0) for key in metric_keys]
        refs["model_chart"].update()

    def refresh_paper() -> None:
        overview = load_overview(config)
        refs["paper_status"].set_text(str(overview.get("paper_status") or "—"))
        refs["paper_nav_detail"].set_text(_vnd(overview.get("paper_latest_nav_vnd")))
        refs["paper_return"].set_text(_percent(overview.get("paper_total_return")))
        refs["paper_drawdown"].set_text(_percent(overview.get("paper_max_drawdown")))
        refs["paper_fill"].set_text(str(overview.get("paper_fill_count") or 0))
        refs["paper_pending"].set_text(str(overview.get("paper_pending_order_count") or 0))
        nav = load_paper_nav(config)
        refs["paper_nav_chart"].options["xAxis"]["data"] = [row.get("ngay", "") for row in nav]
        refs["paper_nav_chart"].options["series"][0]["data"] = [
            _safe_chart_value(row.get("nav")) for row in nav
        ]
        refs["paper_nav_chart"].update()
        positions = load_paper_positions(config)
        if positions:
            latest_day = max(row.get("ngay", "") for row in positions)
            positions = [row for row in positions if row.get("ngay") == latest_day]
        refs["positions_table"].columns = _columns(
            positions, ("ngay", "ma", "so_luong", "gia_von", "gia_dong_cua", "gia_tri_thi_truong", "lai_lo_chua_thuc_hien")
        )
        refs["positions_table"].rows = positions
        refs["positions_table"].update()

    def refresh_jobs() -> None:
        jobs = store.recent()
        refs["jobs_table"].rows = jobs
        refs["jobs_table"].update()
        selected = refs["jobs_table"].selected
        job = selected[0] if selected else (store.active() or (jobs[0] if jobs else None))
        if job:
            refs["job_log"].value = read_log_tail(Path(str(job["log_path"])), 500)
            refs["job_log"].update()
        settings = load_overview(config)
        settings_text = {
            "repo_root": settings["repo_root"],
            "data_root": settings["data_root"],
            "listen": f"http://{config.host}:{config.port}",
            "dnse_credentials_loaded": settings["credential_loaded"],
            "prediction_input_present": settings["prediction_input_present"],
            "latest_eod_dir": settings["latest_eod_dir"],
            "latest_paper_snapshot": settings["latest_paper_snapshot"],
            "nicegui_required_version": NICEGUI_VERSION,
            "security": "localhost_only; credentials_not_rendered",
        }
        refs["settings_text"].value = json.dumps(settings_text, ensure_ascii=False, indent=2)
        refs["settings_text"].update()

    def refresh_active_job() -> None:
        active = store.active()
        refs["run_button"].set_enabled(active is None)
        refs["scenario_button"].set_enabled(active is None)
        if active:
            refs["run_status"].set_text(
                f"{active['kind']} · {active['status']} · {active['stage']} · {active['id'][:8]}"
            )
            refs["run_log"].value = read_log_tail(Path(str(active["log_path"])), 300)
            refs["run_log"].update()
            state["last_terminal_job"] = None
        else:
            recent = store.recent(1)
            latest = recent[0] if recent else None
            if latest:
                refs["run_status"].set_text(
                    f"Job gần nhất: {latest['status']} · {latest['stage']} · exit={latest['return_code']}"
                )
                refs["run_log"].value = read_log_tail(Path(str(latest["log_path"])), 300)
                refs["run_log"].update()
                if latest["status"] in {"SUCCESS", "FAILED"} and state.get("last_terminal_job") != latest["id"]:
                    state["last_terminal_job"] = latest["id"]
                    refresh_all()
                    ui.notify(
                        "Pipeline hoàn tất." if latest["status"] == "SUCCESS" else f"Pipeline lỗi: {latest['error']}",
                        type="positive" if latest["status"] == "SUCCESS" else "negative",
                        timeout=8000,
                    )
        header_status.set_text(
            f"Localhost · DNSE {'OK' if os.environ.get('DNSE_API_KEY') and os.environ.get('DNSE_API_SECRET') else 'MISSING'} · "
            f"Job {(active or {}).get('stage', 'rảnh')}"
        )

    def refresh_all() -> None:
        refresh_overview()
        refresh_data()
        refresh_prediction()
        refresh_paper()
        refresh_jobs()

    refs["run_button"].on("click", start_daily)
    refs["scenario_button"].on("click", start_scenario)
    refs["data_refresh_button"].on("click", refresh_data)
    refs["refresh_jobs_button"].on("click", refresh_jobs)
    refs["jobs_table"].on("selection", lambda _: refresh_jobs())
    refs["open_data_button"].on(
        "click",
        lambda: _open_explorer(latest_successful_eod(config.data_root) or config.data_root),
    )
    refs["open_paper_button"].on(
        "click", lambda: _open_explorer(config.paper_state_dir)
    )
    refs["open_logs_button"].on(
        "click", lambda: _open_explorer(config.logs_dir)
    )

    refresh_all()
    ui.timer(1.0, refresh_active_job)


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
    store = JobStore(config.jobs_db)
    store.interrupt_stale_jobs()
    try:
        from nicegui import ui
        import nicegui
    except ImportError as exc:
        raise RuntimeError(
            f"NICEGUI_NOT_INSTALLED: chay bang uv run --with nicegui=={NICEGUI_VERSION}"
        ) from exc
    version = getattr(nicegui, "__version__", "")
    if version and version != NICEGUI_VERSION:
        raise RuntimeError(f"NICEGUI_VERSION_MISMATCH:{version}!={NICEGUI_VERSION}")
    build_app(ui, config, store)
    ui.run(
        host=config.host,
        port=config.port,
        title="VN Quant Local Console",
        reload=False,
        show=True,
        favicon="📈",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
