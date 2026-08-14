"""VN Quant Local Terminal v9: frozen-reference contribution planning."""
from __future__ import annotations

from datetime import timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import web_console_app_v5 as terminal_base
from . import web_console_app_v8 as base
from .contribution_portfolio_v17 import (
    ContributionPlanRequest,
    build_contribution_plan,
)
from .portfolio_planner import PortfolioStore, latest_price_map
from .reference_target_v17 import load_latest_reference_target
from .web_local_core import JobStore, LocalWebConfig

NICEGUI_VERSION = base.NICEGUI_VERSION
APP_TITLE = base.APP_TITLE
VN_TZ = timezone(timedelta(hours=7))


def _parser():
    return base._parser()


def _vnd(value: object) -> str:
    return terminal_base._vnd(value)


def _pct(value: object) -> str:
    return terminal_base._pct(value, already_percent=True)


def build_app(ui: Any, config: LocalWebConfig, jobs: JobStore, portfolio: PortfolioStore) -> None:
    base.build_app(ui, config, jobs, portfolio)
    ui.add_css("""
        #capital { display:none !important; }
        .v9-contribution-button { position:fixed; right:24px; bottom:24px; z-index:700; }
        .v9-contribution-dialog { width:min(1220px,96vw) !important; max-width:1220px !important; }
    """)
    refs: dict[str, Any] = {}

    with ui.dialog() as dialog, ui.card().classes("v9-contribution-dialog p-4"):
        with ui.row().classes("w-full items-center justify-between gap-3"):
            with ui.column().classes("gap-0"):
                ui.label("Góp vốn định kỳ · frozen reference v15").classes("text-h6")
                ui.label(
                    "Đọc danh mục DNSE hiện tại, dùng target tháng gần nhất và chỉ đề xuất mua thêm."
                ).classes("text-caption text-grey-7")
            ui.button(icon="close", on_click=dialog.close).props("flat round")
        with ui.row().classes("w-full items-end gap-3 flex-wrap mt-3"):
            refs["amount"] = ui.number(
                "Số tiền mới VND",
                value=300_000,
                min=0,
                step=100_000,
            ).classes("w-56")
            refs["include_cash"] = ui.checkbox(
                "Dùng thêm settled cash đang có",
                value=False,
            )
            refs["lot"] = ui.number("Lot", value=100, min=1, step=1).classes("w-28")
            refs["require_sector"] = ui.checkbox(
                "Bắt buộc đủ sector để áp trần 25%",
                value=False,
            )
            refs["run"] = ui.button(
                "TÍNH PHẦN MUA THÊM",
                icon="calculate",
            ).props("unelevated no-caps color=accent")
        refs["source"] = ui.label("Chưa đọc frozen reference signal.").classes(
            "text-caption text-grey-7 mt-2"
        )
        refs["summary"] = ui.label(
            "T+1 chỉ là execution; quality của model được đánh giá theo horizon tháng."
        ).classes("text-body2 mt-2")
        refs["warning"] = ui.label("").classes("text-caption text-warning")
        refs["table"] = ui.table(
            columns=[
                {"name": "rank", "label": "Hạng", "field": "rank", "sortable": True},
                {"name": "symbol", "label": "Mã", "field": "symbol", "sortable": True},
                {"name": "current_quantity", "label": "Đang có", "field": "current_quantity"},
                {"name": "current_weight", "label": "Hiện tại", "field": "current_weight"},
                {"name": "target_weight", "label": "Target", "field": "target_weight"},
                {"name": "buy_quantity", "label": "Mua thêm", "field": "buy_quantity"},
                {"name": "cost", "label": "All-in", "field": "cost"},
                {"name": "post_weight", "label": "Sau mua", "field": "post_weight"},
                {"name": "gap_after", "label": "Còn thiếu", "field": "gap_after"},
                {"name": "status", "label": "Trạng thái", "field": "status"},
            ],
            rows=[],
            row_key="symbol",
            pagination=15,
        ).classes("w-full mt-3").props("flat bordered dense")

    def run_plan() -> None:
        refs["run"].set_enabled(False)
        try:
            target = load_latest_reference_target(config.data_root)
            run, paths, _, _, _, current_predictions, _ = terminal_base._latest_bundle(config)
            price_rows = terminal_base._csv(paths["publication"], limit=10_000_000)
            prices, price_day = latest_price_map(price_rows)
            sector_map = {
                str(row.get("symbol") or row.get("ma") or "").strip().upper():
                str(row.get("sector") or row.get("industry") or "").strip()
                for row in current_predictions
                if str(row.get("symbol") or row.get("ma") or "").strip()
                and str(row.get("sector") or row.get("industry") or "").strip()
            }
            request = ContributionPlanRequest(
                extra_cash_vnd=int(refs["amount"].value or 0),
                settled_cash_vnd=portfolio.get_current_cash(),
                include_settled_cash=bool(refs["include_cash"].value),
                lot_size=int(refs["lot"].value or 100),
                buy_fee_bps=Decimal("2.7"),
                slippage_bps=Decimal("5"),
                max_symbol_weight=Decimal("0.15"),
                max_sector_weight=Decimal("0.25"),
                require_sector_data=bool(refs["require_sector"].value),
            )
            plan = build_contribution_plan(
                holdings=portfolio.list_holdings(),
                price_vnd=prices,
                allocation_rows=target["allocation_rows"],
                predictions=target["predictions"],
                model=target["model"],
                request=request,
                sector_by_symbol=sector_map,
            )
            portfolio.record_plan(plan)
            rows = [
                {
                    "rank": raw.get("rank"),
                    "symbol": raw.get("symbol"),
                    "current_quantity": raw.get("current_quantity"),
                    "current_weight": _pct(raw.get("current_weight_pct")),
                    "target_weight": _pct(raw.get("target_weight_pct")),
                    "buy_quantity": raw.get("recommended_buy_quantity"),
                    "cost": _vnd(raw.get("estimated_all_in_cost_vnd")),
                    "post_weight": _pct(raw.get("post_weight_pct")),
                    "gap_after": _vnd(raw.get("gap_after_vnd")),
                    "status": raw.get("status"),
                }
                for raw in plan.get("rows", [])
                if isinstance(raw, Mapping)
            ]
            refs["table"].rows = rows
            refs["table"].update()
            refs["source"].set_text(
                f"Signal {target['signal_date']} · {target['champion_model']} · "
                f"policy {target['policy_id']} · giá {price_day} · nguồn {run.name}"
            )
            refs["summary"].set_text(
                f"Tiền mới {_vnd(plan['extra_cash_vnd'])} · dự kiến mua "
                f"{_vnd(plan['estimated_spend_vnd'])} · còn "
                f"{_vnd(plan['estimated_remaining_vnd'])} · trạng thái "
                f"{plan['contribution_status']} · thiếu tới lot kế tiếp "
                f"{_vnd(plan['cash_shortfall_to_next_lot_vnd'])}."
            )
            warning_parts = list(plan.get("warnings", []))
            warning_parts.extend(plan.get("hard_risk_breaches", []))
            refs["warning"].set_text(" · ".join(str(item) for item in warning_parts))
            ui.notify(
                "Đã tính phần mua thêm; không có lệnh thật được gửi.",
                type="positive",
            )
        except Exception as exc:
            refs["summary"].set_text(f"{type(exc).__name__}: {exc}")
            ui.notify("Không tạo được kế hoạch góp vốn.", type="negative", timeout=9000)
        finally:
            refs["run"].set_enabled(True)

    refs["run"].on("click", run_plan)
    with ui.button(
        "GÓP VỐN ĐỊNH KỲ",
        icon="savings",
        on_click=dialog.open,
    ).classes("v9-contribution-button"):
        pass


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
    config.data_root.mkdir(parents=True, exist_ok=True)
    jobs = JobStore(config.jobs_db)
    jobs.interrupt_stale_jobs()
    portfolio = PortfolioStore(config.ui_state_dir / "portfolio.sqlite3")
    try:
        import nicegui
        from nicegui import app, ui
    except ImportError as exc:
        raise RuntimeError(f"NICEGUI_NOT_INSTALLED:{NICEGUI_VERSION}") from exc

    @app.get("/healthz")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app": "vn-quant-local-terminal",
            "version": "9",
            "nicegui_version": NICEGUI_VERSION,
            "monthly_model_horizon": True,
            "periodic_contribution_allocator": True,
            "frozen_reference_target": True,
            "dnse_portfolio_aware": True,
            "buy_only": True,
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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
