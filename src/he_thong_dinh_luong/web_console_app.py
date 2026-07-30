"""VN Quant Local Console: EOD, model, allocation, portfolio va paper trading.

Entrypoint duoc thiet ke de chay bang ``python -m``. Trang goc la explicit page;
khong dung NiceGUI auto-index vi auto-index co the thuc thi lai file module va lam
mat package context. Moi refresh artifact deu duoc co lap loi de mot file hong
khong bien thanh HTTP 500 cho toan bo giao dien.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Sequence

from he_thong_dinh_luong.portfolio_planner import (
    ALLOCATOR_REGISTRY,
    MODEL_REGISTRY,
    Holding,
    PlanRequest,
    PortfolioStore,
    build_incremental_plan,
    holdings_as_rows,
    latest_price_map,
)
from he_thong_dinh_luong.web_local_core import (
    DailyPipelineRequest,
    JobStore,
    LocalWebConfig,
    PaperScenarioRequest,
    create_daily_job,
    create_scenario_job,
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
APP_TITLE = "VN Quant Local Console"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.giao_dien_web")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument(
        "--show-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Tu mo trinh duyet; dung --no-show-browser cho CI/smoke test.",
    )
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


def _chart(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _columns(rows: Sequence[Mapping[str, object]], preferred: Sequence[str] = ()) -> list[dict[str, str]]:
    if not rows:
        return []
    names = list(rows[0])
    ordered = [name for name in preferred if name in names]
    ordered.extend(name for name in names if name not in ordered)
    labels = {
        "symbol": "Mã", "ma": "Mã", "ngay": "Ngày", "champion_rank": "Hạng",
        "rank": "Hạng", "target_weight_pct": "Tỷ trọng mục tiêu %",
        "technical_weight_pct": "Tỷ trọng kỹ thuật %", "quantity": "Số lượng",
        "average_cost_vnd": "Giá vốn VND", "latest_price_vnd": "Giá mới nhất VND",
        "market_value_vnd": "Giá trị thị trường", "unrealized_pnl_vnd": "Lãi/lỗ chưa chốt",
        "recommended_buy_quantity": "Mua thêm", "estimated_all_in_cost_vnd": "Chi phí ước tính",
        "post_weight_pct": "Tỷ trọng sau mua %", "current_weight_pct": "Tỷ trọng hiện tại %",
        "status": "Trạng thái", "action": "Hành động",
    }
    return [
        {
            "name": name,
            "label": labels.get(name, name.replace("_", " ").title()),
            "field": name,
            "sortable": True,
            "align": "left",
        }
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


def build_app(ui: Any, config: LocalWebConfig, jobs: JobStore, portfolio: PortfolioStore) -> None:
    """Lap rap mot client page; moi loi artifact duoc hien tren banner thay vi 500."""
    ui.colors(primary="#17324d", secondary="#42657f", accent="#0f766e", positive="#177245", negative="#b42318")
    ui.add_css("""
        body { background: #f3f6f9; color: #172b3a; }
        .q-header { box-shadow: 0 1px 8px rgba(15, 23, 42, .14); }
        .shell { max-width: 1680px; margin: 0 auto; }
        .metric-card { min-width: 180px; flex: 1 1 180px; border: 1px solid #e2e8f0; box-shadow: none; }
        .metric-value { font-size: 1.45rem; font-weight: 750; line-height: 1.2; }
        .section-title { font-size: 1.1rem; font-weight: 750; color: #17324d; }
        .section-subtitle { color: #5b7083; font-size: .92rem; }
        .panel { border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(15, 23, 42, .04); }
        .mono-box textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .warning-banner { border-left: 5px solid #d97706; }
        .q-tab { min-height: 48px; }
    """)

    refs: dict[str, Any] = {}
    state: dict[str, object] = {"last_terminal_job": None, "errors": {}, "last_plan": None}

    def metric_card(title: str, key: str, note: str = "") -> None:
        with ui.card().classes("metric-card"):
            ui.label(title).classes("text-caption text-grey-7")
            refs[key] = ui.label("—").classes("metric-value")
            if note:
                ui.label(note).classes("text-caption text-grey-6")

    def panel_title(title: str, subtitle: str = "") -> None:
        ui.label(title).classes("section-title")
        if subtitle:
            ui.label(subtitle).classes("section-subtitle")

    with ui.header().classes("items-center justify-between bg-primary text-white px-5"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("monitoring", size="32px")
            with ui.column().classes("gap-0"):
                ui.label(APP_TITLE).classes("text-h6")
                ui.label("Local-first · DNSE canonical · model gate · portfolio · paper").classes("text-caption")
        with ui.row().classes("items-center gap-3"):
            refs["header_status"] = ui.label("Đang kiểm tra...").classes("text-caption")
            ui.badge("LOCALHOST", color="accent").props("outline")

    tabs = ui.tabs().classes("w-full bg-white shadow-sm")
    with tabs:
        tab_overview = ui.tab("Tổng quan", icon="space_dashboard")
        tab_run = ui.tab("Chạy pipeline", icon="play_circle")
        tab_data = ui.tab("Dữ liệu", icon="database")
        tab_prediction = ui.tab("Tín hiệu", icon="leaderboard")
        tab_portfolio = ui.tab("Danh mục & tiền mới", icon="account_balance_wallet")
        tab_backtest = ui.tab("Kiểm định", icon="science")
        tab_paper = ui.tab("Paper trading", icon="receipt_long")
        tab_jobs = ui.tab("Vận hành", icon="terminal")

    refs["error_banner"] = ui.banner().classes("hidden warning-banner bg-orange-1 text-orange-10 w-full")

    with ui.tab_panels(tabs, value=tab_overview).classes("w-full bg-transparent shell"):
        with ui.tab_panel(tab_overview):
            panel_title("Bức tranh hệ thống", "Thông tin mới nhất từ artifact đã công bố, không đọc dữ liệu tạm đang chạy.")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric_card("Phiên dữ liệu", "session_date")
                metric_card("Coverage DNSE", "primary_coverage")
                metric_card("Champion", "champion_model")
                metric_card("Market regime", "market_regime")
                metric_card("Vốn kỹ thuật", "capital_budget")
                metric_card("NAV paper", "paper_nav")
            with ui.row().classes("w-full gap-4 items-stretch flex-wrap"):
                with ui.card().classes("panel grow min-w-[620px]"):
                    panel_title("Top ranking mới nhất")
                    refs["overview_prediction_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=10).classes("w-full")
                with ui.card().classes("panel grow min-w-[460px]"):
                    panel_title("NAV paper")
                    refs["overview_nav_chart"] = ui.echart({
                        "xAxis": {"type": "category", "data": []},
                        "yAxis": {"type": "value", "scale": True},
                        "tooltip": {"trigger": "axis"},
                        "series": [{"type": "line", "data": [], "showSymbol": False, "smooth": True}],
                    }).classes("w-full h-80")
            with ui.card().classes("panel w-full"):
                panel_title("Kỷ luật sử dụng")
                ui.label("Ranking và kế hoạch tiền mới là công cụ kỹ thuật/paper. Research eligible vẫn false; không có chức năng gửi lệnh thật.").classes("text-body2")

        with ui.tab_panel(tab_run):
            panel_title("Một nút chạy toàn pipeline", "Chỉ tải các phiên chưa có, sau đó quality → feature → model → allocation → paper.")
            with ui.card().classes("panel w-full"):
                with ui.row().classes("w-full gap-4 items-end flex-wrap"):
                    refs["target_date"] = ui.input("Ngày mục tiêu; để trống = hôm nay", value="").classes("w-72")
                    refs["secondary_source"] = ui.select({"vci": "VCI", "kbs": "KBS"}, value="vci", label="Nguồn kiểm tra advisory").classes("w-52")
                    refs["sample_size"] = ui.number("Số mã kiểm tra", value=20, min=0, step=1).classes("w-44")
                    refs["run_button"] = ui.button("LẤY DATA + MODEL + PHÂN BỔ + PAPER", icon="play_arrow").props("unelevated size=lg")
                with ui.expansion("Vốn và chi phí paper", icon="tune").classes("w-full"):
                    with ui.row().classes("gap-4 flex-wrap"):
                        refs["initial_capital"] = ui.number("Vốn paper VND", value=1_000_000_000, min=1_000_000, step=1_000_000)
                        refs["buy_fee"] = ui.number("Phí mua bps", value=15, min=0, step=1)
                        refs["sell_fee"] = ui.number("Phí bán bps", value=15, min=0, step=1)
                        refs["sell_tax"] = ui.number("Thuế bán bps", value=100, min=0, step=1)
                        refs["slippage"] = ui.number("Slippage bps", value=10, min=0, step=1)
                        refs["lot_size"] = ui.number("Lot", value=100, min=1, step=1)
                refs["run_status"] = ui.label("Không có job đang chạy.").classes("text-body1")
                refs["run_log"] = ui.textarea("Log sống", value="").props("readonly autogrow").classes("w-full mono-box")

        with ui.tab_panel(tab_data):
            panel_title("Dữ liệu model đang dùng", "Publication sau quality gate; raw evidence vẫn nằm trong thư mục run và không nằm trong ZIP kết quả.")
            with ui.row().classes("items-end gap-3 flex-wrap"):
                refs["data_symbol"] = ui.input("Mã", value="HPG").classes("w-40")
                refs["data_limit"] = ui.number("Số dòng", value=120, min=10, max=3000, step=10)
                refs["data_refresh_button"] = ui.button("Đọc dữ liệu", icon="search")
                refs["open_data_button"] = ui.button("Mở thư mục EOD", icon="folder_open").props("outline")
            refs["data_table"] = ui.table(columns=[], rows=[], row_key="ngay", pagination=25).classes("w-full")
            with ui.card().classes("panel w-full"):
                panel_title("Quality report")
                refs["quality_text"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono-box")

        with ui.tab_panel(tab_prediction):
            panel_title("Tín hiệu, model gate và target weights")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric_card("Champion", "pred_champion")
                metric_card("Regime", "pred_regime")
                metric_card("Vốn được phép", "pred_budget")
                metric_card("Ứng viên", "pred_candidates")
            with ui.card().classes("panel w-full"):
                panel_title("Toàn bộ ranking")
                refs["prediction_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=25).classes("w-full")
            with ui.card().classes("panel w-full"):
                panel_title("Danh mục mục tiêu của tín hiệu mới nhất")
                refs["allocation_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=20).classes("w-full")

        with ui.tab_panel(tab_portfolio):
            panel_title("Danh mục thực tế và tiền mới", "Lưu local trên máy. Hệ thống tính khoảng thiếu so với target và đề xuất số lượng mua theo lot; không gửi lệnh.")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric_card("Giá trị cổ phiếu", "actual_market_value")
                metric_card("Tiền mặt hiện có", "actual_cash")
                metric_card("Tổng tài sản", "actual_total")
                metric_card("Tiền dự kiến giải ngân", "plan_spend")
                metric_card("Tiền còn lại", "plan_remaining")
            with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                with ui.card().classes("panel grow min-w-[520px]"):
                    panel_title("Khai báo vị thế hiện tại", "Giá vốn nhập theo VND/cổ phiếu; số lượng 0 sẽ xóa vị thế.")
                    with ui.row().classes("gap-3 items-end flex-wrap"):
                        refs["holding_symbol"] = ui.input("Mã", value="HPG").classes("w-32")
                        refs["holding_quantity"] = ui.number("Số lượng", value=0, min=0, step=100)
                        refs["holding_cost"] = ui.number("Giá vốn VND/cp", value=0, min=0, step=100)
                        refs["holding_save"] = ui.button("Lưu vị thế", icon="save")
                        refs["holding_delete"] = ui.button("Xóa mã", icon="delete").props("outline color=negative")
                    refs["holdings_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=20).classes("w-full")
                    with ui.row().classes("gap-3 items-end"):
                        refs["current_cash"] = ui.number("Tiền mặt hiện có VND", value=0, min=0, step=1_000_000)
                        refs["cash_save"] = ui.button("Lưu tiền mặt", icon="savings")
                with ui.card().classes("panel grow min-w-[520px]"):
                    panel_title("Phân tích tiền nạp thêm", "Mặc định chỉ dùng tiền mới; có thể cho phép dùng cả tiền mặt hiện có.")
                    with ui.row().classes("gap-3 items-end flex-wrap"):
                        refs["extra_cash"] = ui.number("Tiền mới VND", value=100_000_000, min=0, step=1_000_000)
                        refs["include_cash"] = ui.switch("Dùng cả tiền mặt hiện có", value=False)
                        refs["plan_lot"] = ui.number("Lot", value=100, min=1, step=1)
                        refs["plan_fee"] = ui.number("Phí mua bps", value=15, min=0)
                        refs["plan_slippage"] = ui.number("Slippage bps", value=10, min=0)
                        refs["analyze_cash"] = ui.button("PHÂN TÍCH TOÀN CẢNH & CHIA TIỀN", icon="calculate").props("unelevated")
                    refs["market_context"] = ui.textarea("Toàn cảnh thị trường", value="").props("readonly autogrow").classes("w-full mono-box")
            with ui.card().classes("panel w-full"):
                panel_title("Kế hoạch mua bổ sung", "Giá thực thi chỉ là ước tính từ close mới nhất; số lượng đã làm tròn theo lot.")
                refs["plan_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=25).classes("w-full")
                refs["plan_limits"] = ui.label().classes("text-caption text-orange-9")
            with ui.card().classes("panel w-full"):
                panel_title("Lịch sử kế hoạch")
                refs["plan_history"] = ui.table(columns=[], rows=[], row_key="id", pagination=10).classes("w-full")

        with ui.tab_panel(tab_backtest):
            panel_title("Kiểm định model và replay tín hiệu OOS đã ghi nhận")
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
            with ui.card().classes("panel w-full"):
                panel_title("Replay paper scenario", "Chỉ dùng tín hiệu đã được ghi bất biến; không dựng dữ liệu PIT giả.")
                with ui.row().classes("gap-4 items-end flex-wrap"):
                    refs["scenario_capital"] = ui.number("Vốn VND", value=1_000_000_000, min=1_000_000, step=1_000_000)
                    refs["scenario_buy_fee"] = ui.number("Phí mua", value=15, min=0)
                    refs["scenario_sell_fee"] = ui.number("Phí bán", value=15, min=0)
                    refs["scenario_tax"] = ui.number("Thuế bán", value=100, min=0)
                    refs["scenario_slippage"] = ui.number("Slippage", value=10, min=0)
                    refs["scenario_lot"] = ui.number("Lot", value=100, min=1)
                    refs["scenario_button"] = ui.button("Chạy scenario", icon="replay")
                refs["scenario_status"] = ui.label("Chưa chạy scenario.")

        with ui.tab_panel(tab_paper):
            panel_title("Paper trading OOS sống")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric_card("Trạng thái", "paper_status")
                metric_card("NAV", "paper_nav_detail")
                metric_card("Lợi nhuận", "paper_return")
                metric_card("Max drawdown", "paper_drawdown")
                metric_card("Fill", "paper_fill")
                metric_card("Lệnh chờ", "paper_pending")
            refs["paper_nav_chart"] = ui.echart({
                "xAxis": {"type": "category", "data": []},
                "yAxis": {"type": "value", "scale": True},
                "tooltip": {"trigger": "axis"},
                "dataZoom": [{"type": "inside"}, {"type": "slider"}],
                "series": [{"type": "line", "data": [], "showSymbol": False, "smooth": True}],
            }).classes("w-full h-96")
            with ui.card().classes("panel w-full"):
                panel_title("Vị thế paper gần nhất")
                refs["positions_table"] = ui.table(columns=[], rows=[], row_key="ma", pagination=25).classes("w-full")
                refs["open_paper_button"] = ui.button("Mở thư mục paper", icon="folder_open").props("outline")

        with ui.tab_panel(tab_jobs):
            panel_title("Job, log, health và kiến trúc mở rộng")
            with ui.row().classes("gap-3"):
                refs["refresh_jobs_button"] = ui.button("Làm mới", icon="refresh")
                refs["open_logs_button"] = ui.button("Mở log", icon="folder_open").props("outline")
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
            refs["job_log"] = ui.textarea("Log job", value="").props("readonly autogrow").classes("w-full mono-box")
            with ui.row().classes("w-full gap-4 flex-wrap"):
                with ui.card().classes("panel grow min-w-[520px]"):
                    panel_title("Cấu hình & health")
                    refs["settings_text"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono-box")
                with ui.card().classes("panel grow min-w-[520px]"):
                    panel_title("Registry model/allocator", "Tích hợp model mới bằng adapter/registry, không gắn logic model vào component UI.")
                    refs["registry_text"] = ui.textarea(value=json.dumps({"models": MODEL_REGISTRY, "allocators": ALLOCATOR_REGISTRY}, ensure_ascii=False, indent=2)).props("readonly autogrow").classes("w-full mono-box")

    def show_errors() -> None:
        errors = state.get("errors", {})
        if isinstance(errors, Mapping) and errors:
            refs["error_banner"].set_text("Một số khối chưa đọc được: " + " | ".join(f"{key}: {value}" for key, value in errors.items()))
            refs["error_banner"].classes(remove="hidden")
        else:
            refs["error_banner"].classes(add="hidden")

    def guarded(name: str, callback: Callable[[], None]) -> None:
        try:
            callback()
            errors = state.get("errors")
            if isinstance(errors, dict):
                errors.pop(name, None)
        except Exception as exc:
            errors = state.get("errors")
            if isinstance(errors, dict):
                errors[name] = f"{type(exc).__name__}:{exc}"
        show_errors()

    async def launch_job(job_id: str, steps: Sequence[object]) -> None:
        await asyncio.to_thread(execute_job, store=jobs, job_id=job_id, config=config, steps=steps)

    async def start_daily() -> None:
        try:
            target_text = str(refs["target_date"].value or "").strip()
            request = DailyPipelineRequest(
                target_date=date.fromisoformat(target_text) if target_text else None,
                secondary_source=str(refs["secondary_source"].value),
                crosscheck_sample_size=int(refs["sample_size"].value),
                initial_capital_vnd=int(refs["initial_capital"].value),
                buy_fee_bps=float(refs["buy_fee"].value),
                sell_fee_bps=float(refs["sell_fee"].value),
                sell_tax_bps=float(refs["sell_tax"].value),
                slippage_bps=float(refs["slippage"].value),
                lot_size=int(refs["lot_size"].value),
            )
            job_id, output_dir, steps = create_daily_job(jobs, config, request)
            refs["run_status"].set_text(f"Đã xếp job {job_id[:8]} → {output_dir}")
            ui.notify("Pipeline đã bắt đầu.", type="positive")
            asyncio.create_task(launch_job(job_id, steps))
        except Exception as exc:
            ui.notify(f"Không thể chạy: {type(exc).__name__}: {exc}", type="negative", timeout=9000)

    async def start_scenario() -> None:
        try:
            publication = latest_publication_dir(config)
            if publication is None or latest_paper_snapshot(config.data_root) is None:
                raise ValueError("PAPER_OR_PUBLICATION_NOT_INITIALIZED")
            request = PaperScenarioRequest(
                initial_capital_vnd=int(refs["scenario_capital"].value),
                buy_fee_bps=float(refs["scenario_buy_fee"].value),
                sell_fee_bps=float(refs["scenario_sell_fee"].value),
                sell_tax_bps=float(refs["scenario_tax"].value),
                slippage_bps=float(refs["scenario_slippage"].value),
                lot_size=int(refs["scenario_lot"].value),
            )
            job_id, output_dir, steps = create_scenario_job(jobs, config, request, publication_dir=publication)
            refs["scenario_status"].set_text(f"Đang chạy {job_id[:8]} → {output_dir}")
            asyncio.create_task(launch_job(job_id, steps))
        except Exception as exc:
            ui.notify(f"Không thể chạy scenario: {type(exc).__name__}: {exc}", type="negative", timeout=9000)

    def refresh_overview() -> None:
        overview = load_overview(config)
        refs["session_date"].set_text(str(overview.get("session_date") or "—"))
        refs["primary_coverage"].set_text(_percent(overview.get("primary_coverage")))
        refs["champion_model"].set_text(str(overview.get("champion_model") or "—"))
        refs["market_regime"].set_text(str(overview.get("market_regime") or "—"))
        refs["capital_budget"].set_text(f"{_number(overview.get('capital_budget_pct'), 0)}%" if overview.get("capital_budget_pct") is not None else "—")
        refs["paper_nav"].set_text(_vnd(overview.get("paper_latest_nav_vnd")))
        active = jobs.active()
        refs["header_status"].set_text(f"DNSE {'OK' if overview['credential_loaded'] else 'MISSING'} · Data {overview.get('session_date') or 'chưa có'} · Job {(active or {}).get('stage', 'rảnh')}")
        predictions = load_latest_predictions(config, limit=10)
        refs["overview_prediction_table"].columns = _columns(predictions, ("champion_rank", "symbol", "champion_model", "momentum_12_1", "above_ma250", "technical_weight_pct"))
        refs["overview_prediction_table"].rows = predictions
        refs["overview_prediction_table"].update()
        nav = load_paper_nav(config)
        refs["overview_nav_chart"].options["xAxis"]["data"] = [row.get("ngay", "") for row in nav]
        refs["overview_nav_chart"].options["series"][0]["data"] = [_chart(row.get("nav")) for row in nav]
        refs["overview_nav_chart"].update()

    def refresh_data() -> None:
        rows = load_latest_prices(config, symbol=str(refs["data_symbol"].value or "").strip().upper() or None, limit=int(refs["data_limit"].value or 120))
        refs["data_table"].columns = _columns(rows, ("ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong", "nguon", "phien_ban"))
        refs["data_table"].rows = rows
        refs["data_table"].update()
        quality = load_quality_report(config)
        compact = {key: quality.get(key) for key in (
            "status", "quality_tier", "session_date", "base_latest_date", "required_incremental_sessions",
            "symbol_count", "accepted_current_count", "primary_coverage", "crosscheck_sample_count",
            "secondary_match_ratio", "secondary_error_symbol_count", "benchmark_crosscheck",
        ) if key in quality}
        refs["quality_text"].value = json.dumps(compact, ensure_ascii=False, indent=2)
        refs["quality_text"].update()

    def refresh_prediction() -> None:
        predictions = load_latest_predictions(config)
        allocation = load_latest_allocation(config)
        model = load_model_comparison(config)
        refs["prediction_table"].columns = _columns(predictions, ("champion_rank", "symbol", "selected_top_k", "technical_weight_pct", "momentum_12_1", "above_ma250", "relative_strength_120"))
        refs["prediction_table"].rows = predictions
        refs["prediction_table"].update()
        refs["allocation_table"].columns = _columns(allocation, ("rank", "symbol", "target_weight_pct", "champion_model", "status"))
        refs["allocation_table"].rows = allocation
        refs["allocation_table"].update()
        refs["pred_champion"].set_text(str(model.get("champion_model") or "—"))
        refs["pred_regime"].set_text(str(model.get("market_regime") or "—"))
        refs["pred_budget"].set_text(f"{_number(model.get('capital_budget_pct'), 0)}%" if model.get("capital_budget_pct") is not None else "—")
        refs["pred_candidates"].set_text(str(model.get("forward_candidate_count") or "—"))
        momentum = _metric_values(model, "momentum_validation")
        lightgbm = _metric_values(model, "lightgbm_validation")
        keys = ("mean_rank_ic", "precision_at_k", "top_k_relative_return", "mean_set_turnover")
        refs["model_chart"].options["series"][0]["data"] = [momentum.get(key, 0) for key in keys]
        refs["model_chart"].options["series"][1]["data"] = [lightgbm.get(key, 0) for key in keys]
        refs["model_chart"].update()

    def _all_latest_prices() -> tuple[dict[str, Decimal], str]:
        return latest_price_map(load_latest_prices(config, limit=3000))

    def refresh_portfolio() -> None:
        prices, _ = _all_latest_prices()
        holdings = portfolio.list_holdings()
        rows = holdings_as_rows(holdings, prices)
        refs["holdings_table"].columns = _columns(rows, ("symbol", "quantity", "average_cost_vnd", "latest_price_vnd", "market_value_vnd", "unrealized_pnl_vnd"))
        refs["holdings_table"].rows = rows
        refs["holdings_table"].update()
        cash = portfolio.get_current_cash()
        refs["current_cash"].value = cash
        market_value = sum(int(row["market_value_vnd"] or 0) for row in rows)
        refs["actual_market_value"].set_text(_vnd(market_value))
        refs["actual_cash"].set_text(_vnd(cash))
        refs["actual_total"].set_text(_vnd(market_value + cash))
        history = portfolio.recent_plans()
        refs["plan_history"].columns = _columns(history, ("created_at", "signal_date", "allocator", "extra_cash_vnd"))
        refs["plan_history"].rows = history
        refs["plan_history"].update()

    def save_holding() -> None:
        try:
            holding = Holding(str(refs["holding_symbol"].value or ""), int(refs["holding_quantity"].value or 0), Decimal(str(refs["holding_cost"].value or 0)))
            portfolio.upsert_holding(holding)
            guarded("portfolio", refresh_portfolio)
            ui.notify(f"Đã lưu {holding.symbol}.", type="positive")
        except Exception as exc:
            ui.notify(f"Không lưu được vị thế: {type(exc).__name__}: {exc}", type="negative")

    def delete_holding() -> None:
        symbol = str(refs["holding_symbol"].value or "").strip().upper()
        if not symbol:
            ui.notify("Cần nhập mã để xóa.", type="warning")
            return
        portfolio.delete_holding(symbol)
        guarded("portfolio", refresh_portfolio)
        ui.notify(f"Đã xóa {symbol}.", type="positive")

    def save_cash() -> None:
        try:
            portfolio.set_current_cash(int(refs["current_cash"].value or 0))
            guarded("portfolio", refresh_portfolio)
            ui.notify("Đã lưu tiền mặt.", type="positive")
        except Exception as exc:
            ui.notify(f"Không lưu được tiền mặt: {type(exc).__name__}: {exc}", type="negative")

    def analyze_cash() -> None:
        try:
            prices, price_day = _all_latest_prices()
            predictions = load_latest_predictions(config)
            allocation = load_latest_allocation(config)
            model = load_model_comparison(config)
            request = PlanRequest(
                extra_cash_vnd=int(refs["extra_cash"].value or 0),
                current_cash_vnd=portfolio.get_current_cash(),
                include_current_cash=bool(refs["include_cash"].value),
                lot_size=int(refs["plan_lot"].value or 100),
                buy_fee_bps=Decimal(str(refs["plan_fee"].value or 0)),
                slippage_bps=Decimal(str(refs["plan_slippage"].value or 0)),
            )
            plan = build_incremental_plan(holdings=portfolio.list_holdings(), price_vnd=prices, allocation_rows=allocation, predictions=predictions, model=model, request=request)
            plan_id = portfolio.record_plan(plan)
            state["last_plan"] = plan
            rows = plan["rows"]
            refs["plan_table"].columns = _columns(rows, ("rank", "symbol", "status", "current_quantity", "current_weight_pct", "target_weight_pct", "gap_before_vnd", "recommended_buy_quantity", "estimated_all_in_cost_vnd", "post_weight_pct", "above_ma250", "momentum_12_1"))
            refs["plan_table"].rows = rows
            refs["plan_table"].update()
            market = plan["market"]
            context = {
                "price_date": price_day,
                "signal_date": plan["signal_date"],
                "market_regime": market.get("market_regime"),
                "champion_model": market.get("champion_model"),
                "capital_budget_pct": market.get("capital_budget_pct"),
                "breadth_above_ma250": market.get("breadth_above_ma250"),
                "top_selected_above_ma250": market.get("top_selected_above_ma250"),
                "momentum_rank_ic": market.get("momentum_rank_ic"),
                "challenger_rank_ic": market.get("challenger_rank_ic"),
                "estimated_spend_vnd": plan["estimated_spend_vnd"],
                "estimated_remaining_vnd": plan["estimated_remaining_vnd"],
                "outside_target_holdings": plan["outside_target_holdings"],
                "plan_id": plan_id,
            }
            refs["market_context"].value = json.dumps(context, ensure_ascii=False, indent=2)
            refs["market_context"].update()
            refs["plan_spend"].set_text(_vnd(plan["estimated_spend_vnd"]))
            refs["plan_remaining"].set_text(_vnd(plan["estimated_remaining_vnd"]))
            refs["plan_limits"].set_text("Đã kiểm soát lot và trần 15%/mã. Chưa áp trần 25%/ngành vì chưa có sector master PIT tin cậy. Không tự động bán mã đang vượt target.")
            guarded("portfolio", refresh_portfolio)
            ui.notify("Đã tạo kế hoạch tiền mới.", type="positive")
        except Exception as exc:
            ui.notify(f"Không phân tích được: {type(exc).__name__}: {exc}", type="negative", timeout=10000)

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
        refs["paper_nav_chart"].options["series"][0]["data"] = [_chart(row.get("nav")) for row in nav]
        refs["paper_nav_chart"].update()
        positions = load_paper_positions(config)
        if positions:
            latest_day = max(row.get("ngay", "") for row in positions)
            positions = [row for row in positions if row.get("ngay") == latest_day]
        refs["positions_table"].columns = _columns(positions, ("ngay", "ma", "so_luong", "gia_von", "gia_dong_cua", "gia_tri_thi_truong", "lai_lo_chua_thuc_hien"))
        refs["positions_table"].rows = positions
        refs["positions_table"].update()

    def refresh_jobs() -> None:
        rows = jobs.recent()
        refs["jobs_table"].rows = rows
        refs["jobs_table"].update()
        selected = refs["jobs_table"].selected
        job = selected[0] if selected else (jobs.active() or (rows[0] if rows else None))
        if job:
            refs["job_log"].value = read_log_tail(Path(str(job["log_path"])), 500)
            refs["job_log"].update()
        overview = load_overview(config)
        refs["settings_text"].value = json.dumps({
            "repo_root": overview["repo_root"],
            "data_root": overview["data_root"],
            "listen": f"http://{config.host}:{config.port}",
            "health": f"http://{config.host}:{config.port}/healthz",
            "dnse_credentials_loaded": overview["credential_loaded"],
            "prediction_input_present": overview["prediction_input_present"],
            "latest_eod_dir": overview["latest_eod_dir"],
            "latest_paper_snapshot": overview["latest_paper_snapshot"],
            "nicegui_required_version": NICEGUI_VERSION,
            "security": "localhost_only; credentials_not_rendered; no_live_order_api",
        }, ensure_ascii=False, indent=2)
        refs["settings_text"].update()

    def refresh_active_job() -> None:
        active = jobs.active()
        refs["run_button"].set_enabled(active is None)
        refs["scenario_button"].set_enabled(active is None)
        if active:
            refs["run_status"].set_text(f"{active['kind']} · {active['status']} · {active['stage']} · {active['id'][:8]}")
            refs["run_log"].value = read_log_tail(Path(str(active["log_path"])), 300)
            refs["run_log"].update()
            state["last_terminal_job"] = None
        else:
            recent = jobs.recent(1)
            latest = recent[0] if recent else None
            if latest:
                refs["run_status"].set_text(f"Job gần nhất: {latest['status']} · {latest['stage']} · exit={latest['return_code']}")
                refs["run_log"].value = read_log_tail(Path(str(latest["log_path"])), 300)
                refs["run_log"].update()
                if latest["status"] in {"SUCCESS", "FAILED"} and state.get("last_terminal_job") != latest["id"]:
                    state["last_terminal_job"] = latest["id"]
                    refresh_all()
                    ui.notify("Pipeline hoàn tất." if latest["status"] == "SUCCESS" else f"Pipeline lỗi: {latest['error']}", type="positive" if latest["status"] == "SUCCESS" else "negative", timeout=9000)
        refs["header_status"].set_text(f"DNSE {'OK' if os.environ.get('DNSE_API_KEY') and os.environ.get('DNSE_API_SECRET') else 'MISSING'} · Job {(active or {}).get('stage', 'rảnh')}")

    def refresh_all() -> None:
        guarded("overview", refresh_overview)
        guarded("data", refresh_data)
        guarded("prediction", refresh_prediction)
        guarded("portfolio", refresh_portfolio)
        guarded("paper", refresh_paper)
        guarded("jobs", refresh_jobs)

    refs["run_button"].on("click", start_daily)
    refs["scenario_button"].on("click", start_scenario)
    refs["data_refresh_button"].on("click", lambda: guarded("data", refresh_data))
    refs["refresh_jobs_button"].on("click", lambda: guarded("jobs", refresh_jobs))
    refs["jobs_table"].on("selection", lambda _: guarded("jobs", refresh_jobs))
    refs["holding_save"].on("click", save_holding)
    refs["holding_delete"].on("click", delete_holding)
    refs["cash_save"].on("click", save_cash)
    refs["analyze_cash"].on("click", analyze_cash)
    refs["open_data_button"].on("click", lambda: _open_explorer(latest_successful_eod(config.data_root) or config.data_root))
    refs["open_paper_button"].on("click", lambda: _open_explorer(config.paper_state_dir))
    refs["open_logs_button"].on("click", lambda: _open_explorer(config.logs_dir))

    refresh_all()
    ui.timer(1.0, refresh_active_job)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = LocalWebConfig(repo_root=args.repo_root.resolve(), data_root=args.data_root.resolve(), host=args.host, port=args.port)
    if config.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("WEB_LOCALHOST_ONLY")
    if not (config.repo_root / "src" / "he_thong_dinh_luong").is_dir():
        raise ValueError("REPO_ROOT_INVALID")
    config.data_root.mkdir(parents=True, exist_ok=True)
    jobs = JobStore(config.jobs_db)
    jobs.interrupt_stale_jobs()
    portfolio = PortfolioStore(config.ui_state_dir / "portfolio.sqlite3")

    try:
        from nicegui import app, ui
        import nicegui
    except ImportError as exc:
        raise RuntimeError(f"NICEGUI_NOT_INSTALLED: chay bang uv run --with nicegui=={NICEGUI_VERSION}") from exc
    version = getattr(nicegui, "__version__", "")
    if version and version != NICEGUI_VERSION:
        raise RuntimeError(f"NICEGUI_VERSION_MISMATCH:{version}!={NICEGUI_VERSION}")

    @app.get("/healthz")
    async def healthz() -> dict[str, object]:
        return {"status": "ok", "app": "vn-quant-local-console", "nicegui_version": version or NICEGUI_VERSION, "localhost_only": True}

    @ui.page("/")
    def index_page() -> None:
        build_app(ui, config, jobs, portfolio)

    ui.run(host=config.host, port=config.port, title=APP_TITLE, reload=False, show=bool(args.show_browser), favicon="📈")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
