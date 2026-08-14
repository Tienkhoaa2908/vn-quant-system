"""VN Quant Local Terminal V78: C3 tactical operating screen + legacy terminal.

Root page is the operational C3 tactical view. `/terminal` preserves the full V5
terminal. No endpoint sends broker orders; the page is evidence/advisory only.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import web_console_app_v5 as v5
from .portfolio_planner import PortfolioStore
from .web_local_core import JobStore, LocalWebConfig

APP_TITLE = "VN Quant · C3 Tactical"
NICEGUI_VERSION = v5.NICEGUI_VERSION


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError:
        return []


def _pct(value: object) -> str:
    try:
        if value in (None, ""):
            return "—"
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"


def _num(value: object, digits: int = 2) -> str:
    try:
        if value in (None, ""):
            return "—"
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _latest_paths(data_root: Path) -> tuple[Path, Path, Path, Path]:
    root = Path(data_root) / "v78-c3-tactical"
    return (
        root / "LATEST.json",
        root / "v78_tactical_rows.csv",
        root / "v78_incumbent_health.csv",
        root / "v78_emerging_radar.csv",
    )


def _present_tactical(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        canonical = str(row.get("canonical_rank") or "")
        if canonical in {"1000000000", "10000000000", "999999999"}:
            canonical = "—"
        output.append({
            "symbol": row.get("symbol"),
            "month_rank": canonical or "—",
            "now_rank": row.get("preview_rank") or "—",
            "period": _pct(row.get("period_return")),
            "alpha": _pct(row.get("period_relative_return")),
            "rel5": _pct(row.get("relative_5")),
            "dd20": _pct(row.get("drawdown_20")),
            "dd60": _pct(row.get("drawdown_60")),
            "volume": _num(row.get("volume_ratio_5_20")),
            "drag": "↓" if str(row.get("dragging_current_period", "")).lower() in {"true", "1"} else "",
            "ridge": "✓" if str(row.get("ridge_monthly_top10", "")).lower() in {"true", "1"} else "",
            "action": row.get("action"),
            "reason": row.get("reason"),
        })
    return output


def _columns() -> list[dict[str, object]]:
    return [
        {"name": key, "label": label, "field": key, "sortable": True, "align": "left"}
        for key, label in (
            ("symbol", "Mã"), ("month_rank", "Rank tháng"), ("now_rank", "Rank hiện tại"),
            ("period", "P&L kỳ"), ("alpha", "Alpha kỳ"), ("drag", "Kéo xuống"),
            ("rel5", "Rel 5p"), ("dd20", "DD20"), ("dd60", "DD60"),
            ("volume", "Vol 5/20"), ("ridge", "Ridge"), ("action", "Hành động"), ("reason", "Lý do"),
        )
    ]


def build_tactical_page(ui: Any, config: LocalWebConfig) -> None:
    ui.colors(primary="#0b1f33", secondary="#1d3b55", accent="#0f8b8d", positive="#15803d", negative="#b91c1c", warning="#b45309")
    ui.add_css("""
        body { background:#eef2f6; color:#13283a; font-family:Inter,Segoe UI,Arial,sans-serif; }
        .shell { max-width:1820px; margin:0 auto; padding:18px; }
        .surface { background:white; border:1px solid #dbe4ec; border-radius:12px; box-shadow:0 4px 14px rgba(15,35,55,.05); }
        .metric { min-width:180px; flex:1 1 180px; padding:16px; }
        .value { font-size:1.35rem; font-weight:760; color:#102a43; }
        .compact .q-table th { background:#f5f8fb; font-weight:700; }
    """)
    refs: dict[str, Any] = {}

    with ui.header().classes("h-16 items-center justify-between bg-primary text-white px-5"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("radar", size="30px")
            ui.label(APP_TITLE).classes("text-h6")
            ui.badge("C3 MAIN", color="positive")
            ui.badge("ADVISORY · NO LIVE ORDERS", color="warning").props("outline")
        with ui.row().classes("items-center gap-3"):
            ui.link("Terminal đầy đủ", "/terminal").classes("text-white")
            ui.button("Làm mới", icon="refresh", on_click=lambda: refresh()).props("flat color=white no-caps")

    with ui.column().classes("shell w-full gap-4"):
        with ui.card().classes("surface w-full p-5"):
            ui.label("C3 là mô hình chính vận hành").classes("text-h5 text-weight-bold")
            refs["summary"] = ui.label("Đang đọc tactical snapshot...").classes("text-body2 text-grey-7")
        with ui.row().classes("w-full gap-3 flex-wrap"):
            for title, key in (
                ("Ngày dữ liệu", "capture"), ("Signal tháng", "source"),
                ("Top10 cảnh báo", "health_count"), ("Đang kéo xuống", "drag_count"),
                ("Leader đang nổi", "emerging_count"), ("Swap L15", "swap"), ("Regime", "regime"),
            ):
                with ui.card().classes("surface metric"):
                    ui.label(title).classes("text-caption text-grey-7")
                    refs[key] = ui.label("—").classes("value")

        with ui.card().classes("surface w-full p-4"):
            ui.label("Top tháng trước: sức khỏe + P&L thực thi hiện tại").classes("text-h6 text-weight-bold")
            ui.label("P&L kỳ đo từ open phiên đầu sau monthly signal tới close hiện tại; Alpha kỳ trừ VNINDEX cùng calendar. Top10 vẫn hiện dù mất eligibility. R07/R08 chỉ cảnh báo.").classes("text-caption text-grey-7")
            refs["health"] = ui.table(columns=_columns(), rows=[], row_key="symbol", pagination=15).classes("w-full compact").props("flat bordered dense")

        with ui.card().classes("surface w-full p-4"):
            ui.label("Leader intra-month / mã nổi trước cuối tháng").classes("text-h6 text-weight-bold")
            ui.label("L15 chỉ hiện swap candidate khi đủ preview persistence + relative5 >=2% + volume ratio >=1. Nếu chưa đủ thì chỉ WATCH_EMERGING.").classes("text-caption text-grey-7")
            refs["emerging"] = ui.table(columns=_columns(), rows=[], row_key="symbol", pagination=15).classes("w-full compact").props("flat bordered dense")

        with ui.card().classes("surface w-full p-4"):
            ui.label("Toàn bộ tactical ranking").classes("text-h6 text-weight-bold")
            refs["all"] = ui.table(columns=_columns(), rows=[], row_key="symbol", pagination=25).classes("w-full compact").props("flat bordered dense")

        with ui.card().classes("surface w-full p-4"):
            ui.label("Backtest regime gần đây: 6 / 12 / 18 tháng").classes("text-h6 text-weight-bold")
            ui.label("Chỉ dùng để xem lớp phụ có hợp với regime gần đây không; không thay bằng chứng dài hạn của C3.").classes("text-caption text-grey-7")
            refs["recent"] = ui.table(columns=[
                {"name":"family","label":"Lane","field":"family"},
                {"name":"window","label":"Tháng","field":"window"},
                {"name":"candidate","label":"Candidate","field":"candidate"},
                {"name":"base","label":"C3/Base","field":"base"},
                {"name":"cand","label":"Candidate return","field":"cand"},
                {"name":"delta","label":"Delta","field":"delta"},
                {"name":"bench","label":"VNINDEX","field":"bench"},
            ], rows=[], pagination=20).classes("w-full compact").props("flat bordered dense")
            refs["recent_note"] = ui.label("—").classes("text-caption text-grey-7")

    def refresh() -> None:
        report_path, tactical_path, health_path, emerging_path = _latest_paths(config.data_root)
        report = _read_json(report_path)
        tactical = _read_csv(tactical_path)
        health = _read_csv(health_path)
        emerging = _read_csv(emerging_path)
        if not report:
            refs["summary"].set_text("Chưa có V78 snapshot. Chạy scripts/run_v78_c3_tactical_terminal_gitbash.sh trước.")
            return
        refs["summary"].set_text(
            f"Champion {report.get('operational_champion')} · secondary {report.get('secondary_model')} chỉ confirmation · "
            f"P&L incumbent đo {report.get('period_execution_start_day')} → {report.get('capture_day')} · tactical chỉ tư vấn intra-month."
        )
        refs["capture"].set_text(str(report.get("capture_day") or "—"))
        refs["source"].set_text(str(report.get("source_monthly_signal_day") or "—"))
        refs["health_count"].set_text(str(report.get("incumbent_health_alert_count") or 0))
        refs["drag_count"].set_text(str(report.get("dragging_incumbent_count") or 0))
        refs["emerging_count"].set_text(str(report.get("emerging_radar_count") or 0))
        pair = report.get("l15_swap_pair") if isinstance(report.get("l15_swap_pair"), Mapping) else {}
        refs["swap"].set_text(f"{pair.get('swap_out')} → {pair.get('leader')}" if pair.get("active") else "Chưa có")
        refs["regime"].set_text("RISK ON" if report.get("risk_on") else "RISK OFF")
        refs["all"].rows = _present_tactical(tactical); refs["all"].update()
        refs["health"].rows = _present_tactical(health); refs["health"].update()
        refs["emerging"].rows = _present_tactical(emerging); refs["emerging"].update()
        recent = report.get("recent_regime_evidence") if isinstance(report.get("recent_regime_evidence"), Mapping) else {}
        rows = []
        for family, items in (("V72 overlay", recent.get("v72", [])), ("Ridge", recent.get("ridge", []))):
            if not isinstance(items, list):
                continue
            for raw in items:
                if not isinstance(raw, Mapping):
                    continue
                rows.append({
                    "family": family,
                    "window": raw.get("window_months"),
                    "candidate": raw.get("candidate_id"),
                    "base": _pct(raw.get("baseline_return")),
                    "cand": _pct(raw.get("candidate_return")),
                    "delta": _pct(raw.get("candidate_minus_baseline")),
                    "bench": _pct(raw.get("benchmark_return")),
                })
        refs["recent"].rows = rows; refs["recent"].update()
        refs["recent_note"].set_text(
            "Có recent evidence." if rows else "Chưa tìm thấy monthly-return artifact V72/V76 local; tactical live vẫn hoạt động, recent backtest card sẽ tự có khi artifact tồn tại."
        )

    refresh()
    ui.timer(30.0, refresh)


def main(argv: Sequence[str] | None = None) -> int:
    args = v5._parser().parse_args(argv)
    config = LocalWebConfig(
        repo_root=args.repo_root.resolve(),
        data_root=args.data_root.resolve(),
        host=args.host,
        port=args.port,
    )
    if config.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("WEB_LOCALHOST_ONLY")
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
    def healthz() -> dict[str, object]:
        report_path, *_ = _latest_paths(config.data_root)
        report = _read_json(report_path)
        return {
            "status": "ok",
            "app": "vn-quant-c3-tactical-v78",
            "operational_champion": report.get("operational_champion", "C3_STABLE_3_PAST_IC_SHRUNK"),
            "trading_enabled": False,
            "localhost_only": True,
        }

    @app.get("/api/v78/tactical")
    def tactical_api() -> dict[str, object]:
        report_path, *_ = _latest_paths(config.data_root)
        return _read_json(report_path)

    @ui.page("/")
    def tactical_page() -> None:
        build_tactical_page(ui, config)

    @ui.page("/terminal")
    def legacy_terminal() -> None:
        v5.build_app(ui, config, jobs, portfolio)

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
