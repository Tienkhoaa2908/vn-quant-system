"""VN Quant Local Console v3: anytime snapshot, final EOD, portfolio and paper."""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from he_thong_dinh_luong.eod_hang_ngay import VN_TZ
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
APP_TITLE = "VN Quant Local Console"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.giao_dien_web")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--show-browser", action=argparse.BooleanOptionalAction, default=True)
    return parser


def _json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _csv(path: Path, *, limit: int = 1000, symbol: str | None = None, tail: bool = False) -> list[dict[str, str]]:
    if not path.is_file() or limit <= 0:
        return []
    target = symbol.strip().upper() if symbol else None
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for raw in csv.DictReader(stream):
            row = {str(key): str(value or "") for key, value in raw.items()}
            row_symbol = (row.get("symbol") or row.get("ma") or "").upper()
            if target and row_symbol != target:
                continue
            rows.append(row)
    return rows[-limit:] if tail else rows[:limit]


def _analysis_paths(run: Path) -> dict[str, Path]:
    return {
        "manifest": run / "manifest.json",
        "quality": run / "data_quality_report.json",
        "summary": run / "daily_prediction_summary.txt",
        "prediction": run / "prediction" / "latest_prediction.csv",
        "model": run / "prediction" / "model_comparison.json",
        "allocation": run / "paper_portfolio.csv",
        "publication": run / "updated_publication" / "du_lieu_gia_mo_dong_khoi_luong.csv",
        "snapshot_zip": run / "snapshot_quant_output.zip",
        "final_zip": run / "daily_quant_output.zip",
    }


def _analysis_runs(data_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for pattern in ("anytime-web-*", "snapshot-web-*", "eod-web-*", "eod-dnse-*", "eod-dnse-vci-*"):
        for path in data_root.glob(pattern):
            paths = _analysis_paths(path)
            manifest = _json(paths["manifest"])
            if (
                path.is_dir()
                and manifest.get("status") == "SUCCESS"
                and paths["prediction"].is_file()
                and paths["model"].is_file()
                and paths["allocation"].is_file()
                and paths["publication"].is_file()
            ):
                candidates.append(path.resolve())
    candidates = sorted(set(candidates), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates


def _latest_analysis(data_root: Path) -> Path | None:
    runs = _analysis_runs(data_root)
    return runs[0] if runs else None


def _number(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _percent(value: object, digits: int = 2, *, already_percent: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number if already_percent else number * 100:.{digits}f}%"


def _vnd(value: object) -> str:
    try:
        return f"{float(value):,.0f} ₫"
    except (TypeError, ValueError):
        return "—"


def _columns(rows: Sequence[Mapping[str, object]], preferred: Sequence[str] = ()) -> list[dict[str, str]]:
    if not rows:
        return []
    names = list(rows[0])
    ordered = [name for name in preferred if name in names]
    ordered.extend(name for name in names if name not in ordered)
    labels = {
        "symbol": "Mã", "ma": "Mã", "ngay": "Ngày", "champion_rank": "Hạng",
        "target_weight_pct": "Tỷ trọng mục tiêu %", "technical_weight_pct": "Tỷ trọng %",
        "decision_score": "Điểm quyết định", "reference_confidence": "Độ đồng thuận",
        "momentum_12_1": "Momentum 12-1", "relative_strength_120": "Sức mạnh tương đối",
        "volatility_60": "Biến động 60", "above_ma250": "Trên MA250",
        "recommended_buy_quantity": "Mua thêm", "estimated_all_in_cost_vnd": "Chi phí dự kiến",
        "post_weight_pct": "Tỷ trọng sau mua %", "current_weight_pct": "Tỷ trọng hiện tại %",
        "current_quantity": "Đang có", "latest_price_vnd": "Giá mới nhất", "status": "Trạng thái",
    }
    return [
        {"name": name, "label": labels.get(name, name.replace("_", " ").title()), "field": name, "sortable": True, "align": "left"}
        for name in ordered
    ]


def _open(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"PATH_NOT_FOUND:{path}")
    subprocess.Popen(["explorer.exe", str(path)] if os.name == "nt" else ["xdg-open", str(path)])


def build_app(ui: Any, config: LocalWebConfig, jobs: JobStore, portfolio: PortfolioStore) -> None:
    ui.colors(primary="#17324d", secondary="#42657f", accent="#0f766e", positive="#177245", negative="#b42318")
    ui.add_css("""
        body { background: #f3f6f9; color: #172b3a; }
        .shell { max-width: 1680px; margin: 0 auto; }
        .metric { min-width: 180px; flex: 1 1 180px; border: 1px solid #e2e8f0; box-shadow: none; }
        .metric-value { font-size: 1.42rem; font-weight: 750; line-height: 1.2; }
        .section-title { font-size: 1.12rem; font-weight: 750; color: #17324d; }
        .section-subtitle { color: #5b7083; font-size: .92rem; }
        .panel { border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(15,23,42,.04); }
        .mono textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .status-strip { border-left: 5px solid #0f766e; }
        .warning-strip { border-left: 5px solid #d97706; }
    """)
    refs: dict[str, Any] = {}
    state: dict[str, object] = {"last_job": None, "last_plan": None, "refresh_error": ""}

    def metric(title: str, key: str, note: str = "") -> None:
        with ui.card().classes("metric"):
            ui.label(title).classes("text-caption text-grey-7")
            refs[key] = ui.label("—").classes("metric-value")
            if note:
                ui.label(note).classes("text-caption text-grey-6")

    def title(text: str, subtitle: str = "") -> None:
        ui.label(text).classes("section-title")
        if subtitle:
            ui.label(subtitle).classes("section-subtitle")

    with ui.header().classes("items-center justify-between bg-primary text-white px-5"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("monitoring", size="32px")
            with ui.column().classes("gap-0"):
                ui.label(APP_TITLE).classes("text-h6")
                ui.label("DNSE snapshot mọi lúc · final EOD · model gate · portfolio · paper").classes("text-caption")
        with ui.row().classes("items-center gap-3"):
            refs["header_status"] = ui.label("Đang kiểm tra...").classes("text-caption")
            ui.badge("LOCALHOST", color="accent").props("outline")

    tabs = ui.tabs().classes("w-full bg-white shadow-sm")
    with tabs:
        tab_overview = ui.tab("Tổng quan", icon="space_dashboard")
        tab_run = ui.tab("Chạy phân tích", icon="play_circle")
        tab_data = ui.tab("Dữ liệu", icon="database")
        tab_signal = ui.tab("Tín hiệu", icon="leaderboard")
        tab_portfolio = ui.tab("Danh mục & tiền mới", icon="account_balance_wallet")
        tab_validation = ui.tab("Kiểm định", icon="science")
        tab_paper = ui.tab("Paper trading", icon="receipt_long")
        tab_ops = ui.tab("Vận hành", icon="terminal")

    refs["error_card"] = ui.card().classes("hidden warning-strip bg-orange-1 text-orange-10 w-full shell")
    with refs["error_card"]:
        refs["error_text"] = ui.label("")

    with ui.tab_panels(tabs, value=tab_overview).classes("w-full bg-transparent shell"):
        with ui.tab_panel(tab_overview):
            title("Bức tranh hệ thống", "Snapshot trong phiên được gắn PROVISIONAL; chỉ final EOD mới cập nhật paper chính thức.")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric("Trạng thái dữ liệu", "data_status")
                metric("Phiên phân tích", "session_date")
                metric("Thời điểm chụp", "as_of")
                metric("Coverage DNSE", "coverage")
                metric("Regime", "regime")
                metric("Ngân sách vốn", "budget")
                metric("Vốn triển khai", "deployed")
                metric("NAV paper", "paper_nav")
            with ui.row().classes("w-full gap-4 flex-wrap"):
                with ui.card().classes("panel grow min-w-[720px]"):
                    title("Tín hiệu và tỷ trọng mới nhất")
                    refs["overview_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=10).classes("w-full")
                with ui.card().classes("panel grow min-w-[420px]"):
                    title("NAV paper final")
                    refs["overview_nav"] = ui.echart({
                        "xAxis": {"type": "category", "data": []},
                        "yAxis": {"type": "value", "scale": True},
                        "tooltip": {"trigger": "axis"},
                        "series": [{"type": "line", "data": [], "showSymbol": False, "smooth": True}],
                    }).classes("w-full h-80")
            with ui.card().classes("panel status-strip w-full"):
                refs["overview_note"] = ui.label("")

        with ui.tab_panel(tab_run):
            title("Bấm một nút ở bất kỳ thời điểm nào", "AUTO: trước 18h chạy snapshot DNSE; sau 18h chạy final EOD và cập nhật paper.")
            with ui.card().classes("panel w-full"):
                with ui.row().classes("w-full gap-4 items-end flex-wrap"):
                    refs["run_mode"] = ui.select({
                        "auto": "Tự động: snapshot trước 18h / final sau 18h",
                        "snapshot": "Snapshot ngay bây giờ — không cập nhật paper",
                        "final": "Final EOD — giữ gate 18h",
                    }, value="auto", label="Chế độ").classes("w-96")
                    refs["target_date"] = ui.input("Ngày mục tiêu; để trống = hôm nay", value="").classes("w-64")
                    refs["secondary"] = ui.select({"vci": "VCI", "kbs": "KBS"}, value="vci", label="Nguồn kiểm tra final").classes("w-48")
                    refs["sample_size"] = ui.number("Số mã kiểm tra", value=20, min=0, step=1).classes("w-40")
                    refs["run_button"] = ui.button("LẤY DATA NGAY + PHÂN TÍCH + CHIA VỐN", icon="play_arrow").props("unelevated size=lg")
                with ui.expansion("Vốn và chi phí paper final", icon="tune").classes("w-full"):
                    with ui.row().classes("gap-4 flex-wrap"):
                        refs["paper_capital"] = ui.number("Vốn paper VND", value=1_000_000_000, min=1_000_000, step=1_000_000)
                        refs["buy_fee"] = ui.number("Phí mua bps", value=15, min=0)
                        refs["sell_fee"] = ui.number("Phí bán bps", value=15, min=0)
                        refs["sell_tax"] = ui.number("Thuế bán bps", value=100, min=0)
                        refs["slippage"] = ui.number("Slippage bps", value=10, min=0)
                        refs["lot"] = ui.number("Lot", value=100, min=1)
                refs["run_status"] = ui.label("Không có job đang chạy.").classes("text-body1")
                refs["run_log"] = ui.textarea("Log sống", value="").props("readonly autogrow").classes("w-full mono")

        with ui.tab_panel(tab_data):
            title("Dữ liệu model đang sử dụng", "Snapshot dùng publication tạm; final publication vẫn bất biến.")
            with ui.row().classes("items-end gap-3"):
                refs["data_symbol"] = ui.input("Mã", value="HPG").classes("w-40")
                refs["data_limit"] = ui.number("Số dòng", value=120, min=10, max=3000, step=10)
                refs["data_refresh"] = ui.button("Đọc dữ liệu", icon="search")
                refs["open_run"] = ui.button("Mở thư mục run", icon="folder_open").props("outline")
            refs["data_table"] = ui.table(columns=[], rows=[], row_key="ngay", pagination=25).classes("w-full")
            with ui.card().classes("panel w-full"):
                title("Chất lượng và finality")
                refs["quality"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono")

        with ui.tab_panel(tab_signal):
            title("Ranking, độ đồng thuận và tỷ trọng tối ưu", "Tỷ trọng = conviction × inverse volatility, có MA250 eligibility và trần 15%/mã.")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric("Champion gate", "signal_champion")
                metric("Reference model", "signal_reference")
                metric("Allocator", "signal_allocator")
                metric("Breadth MA250", "signal_breadth")
            refs["signal_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=25).classes("w-full")
            ui.label("Danh mục mục tiêu").classes("section-title")
            refs["allocation_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=20).classes("w-full")

        with ui.tab_panel(tab_portfolio):
            title("Danh mục thực và tiền mới", "Lưu vị thế hiện tại, sau đó phân tích tiền mới theo target gap, lot, chi phí và trạng thái thị trường.")
            with ui.row().classes("w-full gap-4 flex-wrap items-start"):
                with ui.card().classes("panel grow min-w-[400px]"):
                    title("Khai báo vị thế")
                    with ui.row().classes("gap-3 items-end"):
                        refs["holding_symbol"] = ui.input("Mã").classes("w-28")
                        refs["holding_qty"] = ui.number("Số lượng", value=0, min=0, step=100)
                        refs["holding_cost"] = ui.number("Giá vốn VND/cp", value=0, min=0, step=100)
                        refs["holding_save"] = ui.button("Lưu", icon="save")
                    refs["holdings_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=20).classes("w-full")
                with ui.card().classes("panel grow min-w-[400px]"):
                    title("Tiền mặt và khoản nạp thêm")
                    refs["current_cash"] = ui.number("Tiền mặt hiện có VND", value=0, min=0, step=1_000_000).classes("w-full")
                    refs["cash_save"] = ui.button("Lưu tiền mặt", icon="save").props("outline")
                    refs["extra_cash"] = ui.number("Tiền mới VND", value=100_000_000, min=0, step=1_000_000).classes("w-full")
                    refs["include_cash"] = ui.checkbox("Dùng cả tiền mặt hiện có", value=False)
                    with ui.row().classes("gap-3"):
                        refs["plan_lot"] = ui.number("Lot", value=100, min=1)
                        refs["plan_fee"] = ui.number("Phí mua bps", value=15, min=0)
                        refs["plan_slippage"] = ui.number("Slippage bps", value=10, min=0)
                    refs["plan_button"] = ui.button("PHÂN TÍCH TOÀN CẢNH & CHIA TIỀN", icon="calculate").props("unelevated")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric("Giá trị cổ phiếu", "portfolio_stock")
                metric("Tiền được phép dùng", "portfolio_available")
                metric("Chi phí dự kiến", "portfolio_spent")
                metric("Tiền còn lại", "portfolio_remaining")
                metric("Budget regime", "portfolio_budget")
            refs["plan_table"] = ui.table(columns=[], rows=[], row_key="symbol", pagination=25).classes("w-full")
            refs["plan_note"] = ui.label("").classes("text-body2 text-orange-9")

        with ui.tab_panel(tab_validation):
            title("Kiểm định model", "Champion chỉ đổi khi challenger qua gate OOS; robust ensemble vẫn được hiển thị như điểm tham khảo.")
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
            }).classes("w-full h-96")
            refs["model_text"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono")

        with ui.tab_panel(tab_paper):
            title("Paper trading final", "Snapshot trong phiên không sinh fill và không sửa sổ paper.")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric("Trạng thái", "paper_status")
                metric("NAV", "paper_nav_detail")
                metric("Lợi nhuận", "paper_return")
                metric("Max drawdown", "paper_drawdown")
                metric("Fill", "paper_fills")
                metric("Lệnh chờ", "paper_pending")
            refs["paper_chart"] = ui.echart({
                "xAxis": {"type": "category", "data": []},
                "yAxis": {"type": "value", "scale": True},
                "tooltip": {"trigger": "axis"},
                "dataZoom": [{"type": "inside"}, {"type": "slider"}],
                "series": [{"type": "line", "data": [], "showSymbol": False}],
            }).classes("w-full h-96")
            refs["positions"] = ui.table(columns=[], rows=[], row_key="ma", pagination=25).classes("w-full")

        with ui.tab_panel(tab_ops):
            title("Job, log và registry mở rộng")
            with ui.row().classes("gap-3"):
                refs["ops_refresh"] = ui.button("Làm mới", icon="refresh")
                refs["open_logs"] = ui.button("Mở thư mục log", icon="folder_open").props("outline")
            refs["jobs_table"] = ui.table(columns=[
                {"name": "created_at", "label": "Thời gian", "field": "created_at", "sortable": True},
                {"name": "kind", "label": "Loại", "field": "kind"},
                {"name": "status", "label": "Trạng thái", "field": "status"},
                {"name": "stage", "label": "Bước", "field": "stage"},
                {"name": "return_code", "label": "Exit", "field": "return_code"},
                {"name": "output_dir", "label": "Output", "field": "output_dir"},
            ], rows=[], row_key="id", pagination=20, selection="single").classes("w-full")
            refs["job_log"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono")
            refs["registry"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono")

    def set_error(message: str = "") -> None:
        state["refresh_error"] = message
        refs["error_text"].set_text(message)
        if message:
            refs["error_card"].classes(remove="hidden")
        else:
            refs["error_card"].classes(add="hidden")

    def latest_bundle() -> tuple[Path, dict[str, Path], dict[str, object], dict[str, object], list[dict[str, str]], list[dict[str, str]]]:
        run = _latest_analysis(config.data_root)
        if run is None:
            raise ValueError("CHUA_CO_KET_QUA_PHAN_TICH")
        paths = _analysis_paths(run)
        return run, paths, _json(paths["manifest"]), _json(paths["model"]), _csv(paths["prediction"], limit=500), _csv(paths["allocation"], limit=100)

    def refresh_analysis() -> None:
        try:
            run, paths, manifest, model, predictions, allocation = latest_bundle()
            quality = _json(paths["quality"])
            refs["data_status"].set_text(str(manifest.get("data_status") or quality.get("data_status") or "FINAL"))
            refs["session_date"].set_text(str(manifest.get("session_date") or model.get("signal_date") or "—"))
            refs["as_of"].set_text(str(manifest.get("as_of") or model.get("as_of") or "—").replace("T", " "))
            refs["coverage"].set_text(_percent(manifest.get("primary_coverage") or quality.get("primary_coverage")))
            refs["regime"].set_text(str(model.get("market_regime") or "—"))
            refs["budget"].set_text(_percent(model.get("capital_budget_pct"), already_percent=True))
            refs["deployed"].set_text(_percent(model.get("deployed_budget_pct", model.get("capital_budget_pct")), already_percent=True))
            refs["signal_champion"].set_text(str(model.get("champion_model") or "—"))
            refs["signal_reference"].set_text(str(model.get("reference_model") or "—"))
            refs["signal_allocator"].set_text(str(model.get("allocation_model") or "—"))
            refs["signal_breadth"].set_text(_percent(model.get("breadth_above_ma250")))
            preferred = ("champion_rank", "symbol", "selected_top_k", "technical_weight_pct", "decision_score", "reference_confidence", "above_ma250", "momentum_12_1", "relative_strength_120", "volatility_60")
            refs["overview_table"].columns = _columns(predictions[:10], preferred)
            refs["overview_table"].rows = predictions[:10]
            refs["overview_table"].update()
            refs["signal_table"].columns = _columns(predictions, preferred)
            refs["signal_table"].rows = predictions
            refs["signal_table"].update()
            refs["allocation_table"].columns = _columns(allocation, ("rank", "symbol", "target_weight_pct", "allocation_model", "status"))
            refs["allocation_table"].rows = allocation
            refs["allocation_table"].update()
            status = str(manifest.get("data_status") or "FINAL")
            refs["overview_note"].set_text(
                f"Nguồn đang hiển thị: {run.name} · {status}. Snapshot là provisional; chỉ final EOD cập nhật paper. Research eligible=false."
            )
            compact = {key: quality.get(key) for key in (
                "status", "quality_tier", "data_status", "session_date", "as_of", "base_latest_date", "symbol_count", "accepted_current_count", "primary_coverage", "source_error_count"
            ) if key in quality}
            refs["quality"].value = json.dumps(compact, ensure_ascii=False, indent=2)
            refs["quality"].update()
            metrics = []
            for name in ("momentum_validation", "robust_reference_validation", "lightgbm_validation"):
                raw = model.get(name) if isinstance(model.get(name), Mapping) else {}
                metrics.append([float(raw.get(key, 0) or 0) for key in ("mean_rank_ic", "precision_at_k", "top_k_relative_return", "mean_set_turnover")])
            for index, values in enumerate(metrics):
                refs["model_chart"].options["series"][index]["data"] = values
            refs["model_chart"].update()
            refs["model_text"].value = json.dumps({
                "champion_model": model.get("champion_model"),
                "reference_model": model.get("reference_model"),
                "allocation_model": model.get("allocation_model"),
                "champion_gate_checks": model.get("champion_gate_checks"),
                "momentum_validation": model.get("momentum_validation"),
                "robust_reference_validation": model.get("robust_reference_validation"),
                "lightgbm_validation": model.get("lightgbm_validation"),
                "limitations": model.get("limitations"),
            }, ensure_ascii=False, indent=2)
            refs["model_text"].update()
            refs["header_status"].set_text(
                f"DNSE {'OK' if os.environ.get('DNSE_API_KEY') and os.environ.get('DNSE_API_SECRET') else 'MISSING'} · {status} · Job {(jobs.active() or {}).get('stage', 'rảnh')}"
            )
            set_error("")
        except Exception as exc:
            set_error(f"Không đọc được artifact phân tích: {type(exc).__name__}: {exc}")

    def refresh_data() -> None:
        try:
            run = _latest_analysis(config.data_root)
            if run is None:
                raise ValueError("CHUA_CO_KET_QUA_PHAN_TICH")
            paths = _analysis_paths(run)
            rows = _csv(paths["publication"], limit=int(refs["data_limit"].value or 120), symbol=str(refs["data_symbol"].value or ""), tail=True)
            refs["data_table"].columns = _columns(rows, ("ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong", "nguon", "co_so_gia"))
            refs["data_table"].rows = rows
            refs["data_table"].update()
        except Exception as exc:
            set_error(f"Không đọc được dữ liệu: {type(exc).__name__}: {exc}")

    def refresh_paper() -> None:
        snapshot = latest_paper_snapshot(config.data_root)
        metrics = _json(snapshot / "metrics.json") if snapshot else {}
        refs["paper_status"].set_text(str(metrics.get("status") or "—"))
        refs["paper_nav_detail"].set_text(_vnd(metrics.get("latest_nav_vnd")))
        refs["paper_nav"].set_text(_vnd(metrics.get("latest_nav_vnd")))
        refs["paper_return"].set_text(_percent(metrics.get("total_return")))
        refs["paper_drawdown"].set_text(_percent(metrics.get("max_drawdown")))
        refs["paper_fills"].set_text(str(metrics.get("fill_count") or 0))
        refs["paper_pending"].set_text(str(metrics.get("pending_order_count") or 0))
        nav = load_paper_nav(config)
        x = [row.get("ngay", "") for row in nav]
        y = [float(row.get("nav", 0) or 0) for row in nav]
        for chart in (refs["paper_chart"], refs["overview_nav"]):
            chart.options["xAxis"]["data"] = x
            chart.options["series"][0]["data"] = y
            chart.update()
        positions = load_paper_positions(config)
        if positions:
            latest_day = max(row.get("ngay", "") for row in positions)
            positions = [row for row in positions if row.get("ngay") == latest_day]
        refs["positions"].columns = _columns(positions, ("ngay", "ma", "so_luong", "gia_von", "gia_dong_cua", "gia_tri_thi_truong", "lai_lo_chua_thuc_hien"))
        refs["positions"].rows = positions
        refs["positions"].update()

    def refresh_holdings() -> None:
        run = _latest_analysis(config.data_root)
        price_rows = _csv(_analysis_paths(run)["publication"], limit=10_000_000) if run else []
        prices, _ = latest_price_map(price_rows)
        rows = holdings_as_rows(portfolio.list_holdings(), prices)
        refs["holdings_table"].columns = _columns(rows, ("symbol", "quantity", "average_cost_vnd", "latest_price_vnd", "market_value_vnd", "unrealized_pnl_vnd"))
        refs["holdings_table"].rows = rows
        refs["holdings_table"].update()
        refs["current_cash"].value = portfolio.get_current_cash()
        refs["current_cash"].update()

    def refresh_jobs() -> None:
        rows = jobs.recent()
        refs["jobs_table"].rows = rows
        refs["jobs_table"].update()
        selected = refs["jobs_table"].selected
        job = selected[0] if selected else (jobs.active() or (rows[0] if rows else None))
        if job:
            refs["job_log"].value = read_log_tail(Path(str(job["log_path"])), 500)
            refs["job_log"].update()
        refs["registry"].value = json.dumps({
            "models": MODEL_REGISTRY,
            "allocators": ALLOCATOR_REGISTRY,
            "anytime_modes": {
                "snapshot": "DNSE provisional; no paper mutation",
                "final": "canonical EOD; quality gate; paper update",
            },
        }, ensure_ascii=False, indent=2)
        refs["registry"].update()

    def refresh_all() -> None:
        refresh_analysis()
        refresh_data()
        refresh_paper()
        refresh_holdings()
        refresh_jobs()

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
                "--crosscheck-sample-size", str(int(refs["sample_size"].value)),
                "--initial-capital-vnd", str(int(refs["paper_capital"].value)),
                "--buy-fee-bps", str(float(refs["buy_fee"].value)),
                "--sell-fee-bps", str(float(refs["sell_fee"].value)),
                "--sell-tax-bps", str(float(refs["sell_tax"].value)),
                "--slippage-bps", str(float(refs["slippage"].value)),
                "--lot-size", str(int(refs["lot"].value)),
            ]
            if target is not None:
                command.extend(("--target-date", target.isoformat()))
            log_path = config.logs_dir / f"{output.name}.log"
            job_id = jobs.create_job(
                kind="anytime_analysis",
                output_dir=output,
                log_path=log_path,
                parameters={"mode": refs["run_mode"].value, "target_date": target.isoformat() if target else None},
            )
            refs["run_status"].set_text(f"Đã bắt đầu {job_id[:8]} → {output.name}")
            asyncio.create_task(launch(job_id, PipelineStep("resolve_snapshot_or_final", tuple(command))))
            ui.notify("Đã bắt đầu. Snapshot chạy được ngay; final vẫn giữ gate 18h.", type="positive")
        except Exception as exc:
            ui.notify(f"Không thể chạy: {type(exc).__name__}: {exc}", type="negative", timeout=8000)

    def save_holding() -> None:
        try:
            holding = Holding(
                str(refs["holding_symbol"].value or ""),
                int(refs["holding_qty"].value or 0),
                Decimal(str(refs["holding_cost"].value or 0)),
            )
            portfolio.upsert_holding(holding)
            refresh_holdings()
            ui.notify("Đã lưu vị thế local.", type="positive")
        except Exception as exc:
            ui.notify(f"Không thể lưu: {type(exc).__name__}: {exc}", type="negative")

    def save_cash() -> None:
        try:
            portfolio.set_current_cash(int(refs["current_cash"].value or 0))
            ui.notify("Đã lưu tiền mặt local.", type="positive")
        except Exception as exc:
            ui.notify(f"Không thể lưu tiền mặt: {type(exc).__name__}: {exc}", type="negative")

    def build_plan() -> None:
        try:
            run, paths, _, model, predictions, allocation = latest_bundle()
            price_rows = _csv(paths["publication"], limit=10_000_000)
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
            plan_id = portfolio.record_plan(plan)
            state["last_plan"] = plan
            rows = list(plan.get("rows", []))
            refs["plan_table"].columns = _columns(rows, ("rank", "symbol", "current_quantity", "current_weight_pct", "target_weight_pct", "recommended_buy_quantity", "estimated_all_in_cost_vnd", "post_weight_pct", "status"))
            refs["plan_table"].rows = rows
            refs["plan_table"].update()
            refs["portfolio_stock"].set_text(_vnd(plan.get("current_market_value_vnd")))
            refs["portfolio_available"].set_text(_vnd(plan.get("available_cash_vnd")))
            refs["portfolio_spent"].set_text(_vnd(plan.get("estimated_spend_vnd")))
            refs["portfolio_remaining"].set_text(_vnd(plan.get("remaining_available_cash_vnd")))
            market = plan.get("market_snapshot") if isinstance(plan.get("market_snapshot"), Mapping) else {}
            refs["portfolio_budget"].set_text(_percent(market.get("capital_budget_pct"), already_percent=True))
            refs["plan_note"].set_text(
                f"Plan {plan_id[:8]} · giá ngày {price_day} · nguồn {run.name}. Không tự động bán; sector cap 25% chưa enforce khi chưa có sector master PIT tin cậy."
            )
            ui.notify("Đã tạo kế hoạch tiền mới.", type="positive")
        except Exception as exc:
            ui.notify(f"Không thể chia tiền: {type(exc).__name__}: {exc}", type="negative", timeout=9000)

    def active_tick() -> None:
        active = jobs.active()
        refs["run_button"].set_enabled(active is None)
        if active:
            refs["run_status"].set_text(f"{active['status']} · {active['stage']} · {active['id'][:8]}")
            refs["run_log"].value = read_log_tail(Path(str(active["log_path"])), 350)
            refs["run_log"].update()
            state["last_job"] = None
        else:
            recent = jobs.recent(1)
            latest = recent[0] if recent else None
            if latest:
                refs["run_status"].set_text(f"Job gần nhất: {latest['status']} · {latest['stage']} · exit={latest['return_code']}")
                refs["run_log"].value = read_log_tail(Path(str(latest["log_path"])), 350)
                refs["run_log"].update()
                if latest["status"] in {"SUCCESS", "FAILED"} and state.get("last_job") != latest["id"]:
                    state["last_job"] = latest["id"]
                    refresh_all()
                    ui.notify("Phân tích hoàn tất." if latest["status"] == "SUCCESS" else f"Job lỗi: {latest['error']}", type="positive" if latest["status"] == "SUCCESS" else "negative", timeout=8000)
        refs["header_status"].set_text(
            f"DNSE {'OK' if os.environ.get('DNSE_API_KEY') and os.environ.get('DNSE_API_SECRET') else 'MISSING'} · Job {(active or {}).get('stage', 'rảnh')}"
        )

    refs["run_button"].on("click", start_run)
    refs["data_refresh"].on("click", refresh_data)
    refs["holding_save"].on("click", save_holding)
    refs["cash_save"].on("click", save_cash)
    refs["plan_button"].on("click", build_plan)
    refs["ops_refresh"].on("click", refresh_jobs)
    refs["jobs_table"].on("selection", lambda _: refresh_jobs())
    refs["open_run"].on("click", lambda: _open(_latest_analysis(config.data_root) or config.data_root))
    refs["open_logs"].on("click", lambda: _open(config.logs_dir))
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
            "app": "vn-quant-local-console",
            "version": "3",
            "nicegui_version": NICEGUI_VERSION,
            "localhost_only": True,
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
