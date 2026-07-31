"""VN Quant Local Console v4 with read-only DNSE portfolio intelligence."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from . import web_console_app_v3 as base
from .portfolio_planner import PortfolioStore
from .web_local_core import JobStore, LocalWebConfig
from .web_portfolio_dnse import register_portfolio_page

NICEGUI_VERSION = base.NICEGUI_VERSION
APP_TITLE = base.APP_TITLE
build_app = base.build_app


def main(argv: Sequence[str] | None = None) -> int:
    args = base._parser().parse_args(argv)
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
            "version": "4",
            "nicegui_version": NICEGUI_VERSION,
            "localhost_only": True,
            "dnse_portfolio_read_only": True,
        }

    register_portfolio_page(ui, config)

    @ui.page("/")
    def index() -> None:
        build_app(ui, config, jobs, portfolio)
        ui.button(
            "DANH MỤC DNSE",
            icon="account_balance_wallet",
            on_click=lambda: ui.navigate.to("/portfolio-dnse"),
        ).props("unelevated color=accent").classes("fixed bottom-6 right-6 z-50 shadow-lg")

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
