"""VN Quant Local Terminal v8 with exact research-input lineage."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from . import web_console_app_v5 as base
from .model_lab_core import DEFAULT_MODELS
from .model_lab_web_state import compact_leaderboard, load_model_lab_state, model_lab_grade
from .portfolio_planner import PortfolioStore
from .web_local_core import JobStore, LocalWebConfig, PipelineStep, execute_job, read_log_tail
from .workflow_handoff import load_handoff

NICEGUI_VERSION = base.NICEGUI_VERSION
APP_TITLE = base.APP_TITLE
VN_TZ = timezone(timedelta(hours=7))
TERMINAL = {"SUCCESS", "FAILED", "INTERRUPTED"}


def _parser():
    return base._parser()


def build_app(ui: Any, config: LocalWebConfig, jobs: JobStore, portfolio: PortfolioStore) -> None:
    base.build_app(ui, config, jobs, portfolio)
    ui.add_css("""
        .v8-command { position:fixed; left:18px; right:18px; top:68px; z-index:500;
          background:#ffffff; border:1px solid #cfdbe6; border-top:4px solid #0f8b8d;
          border-radius:12px; box-shadow:0 8px 24px rgba(13,38,59,.13); }
        .v8-stage { min-width:205px; }
        .v8-model-drawer { width:min(1180px,96vw) !important; }
        .terminal-shell { padding-top:132px !important; }
    """)
    refs: dict[str, Any] = {}
    state: dict[str, object] = {"workflow": None, "handled": set()}

    with ui.card().classes("v8-command p-3"):
        with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap"):
            with ui.column().classes("gap-0"):
                ui.label("Workflow thống nhất · lineage v8").classes("text-subtitle1 text-weight-bold")
                refs["summary"] = ui.label(
                    "Dữ liệu → dự đoán → phân bổ → paper → Model Lab trên đúng research package."
                ).classes("text-caption text-grey-7")
            with ui.row().classes("items-end gap-3 flex-wrap"):
                refs["mode"] = ui.select(
                    {"auto": "Tự động", "snapshot": "Snapshot", "final": "Final EOD"},
                    value="auto",
                    label="Dữ liệu",
                ).props("outlined dense").classes("w-36")
                refs["models"] = ui.checkbox("Chạy Model Lab", value=True)
                refs["force"] = ui.checkbox("Chạy lại model", value=False)
                refs["run"] = ui.button("CẬP NHẬT TOÀN BỘ", icon="play_arrow").props(
                    "unelevated no-caps color=accent size=lg"
                )
                refs["details"] = ui.button("KẾT QUẢ MODEL", icon="analytics").props(
                    "outline no-caps color=primary"
                )
        with ui.row().classes("w-full gap-4 flex-wrap mt-2"):
            refs["market_stage"] = ui.label("Dữ liệu: chờ").classes("v8-stage text-caption")
            refs["input_stage"] = ui.label("Research input: chờ").classes("v8-stage text-caption")
            refs["model_stage"] = ui.label("Model Lab: chờ").classes("v8-stage text-caption")
            refs["output_stage"] = ui.label("Output: —").classes("grow text-caption text-grey-7")
        refs["progress"] = ui.linear_progress(value=0).classes("w-full")

    with ui.dialog() as dialog, ui.card().classes("v8-model-drawer p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Model Lab — OOS leaderboard và quality gate").classes("text-h6")
            ui.button(icon="close", on_click=dialog.close).props("flat round")
        with ui.row().classes("w-full gap-4 flex-wrap"):
            refs["grade"] = ui.label("Chưa kiểm định").classes("text-subtitle1 text-weight-bold")
            refs["champion"] = ui.label("Champion: —").classes("text-subtitle1")
            refs["folds"] = ui.label("Fold: —").classes("text-subtitle1")
            refs["watchlist"] = ui.label("Watchlist: —").classes("text-subtitle1")
        refs["model_message"] = ui.label("Chưa có kết quả.").classes("text-body2 text-grey-7")
        refs["table"] = ui.table(
            columns=[
                {"name": "model", "label": "Model", "field": "model", "sortable": True},
                {"name": "family", "label": "Nhóm", "field": "family", "sortable": True},
                {"name": "status", "label": "Trạng thái", "field": "status", "sortable": True},
                {"name": "rank_ic", "label": "Rank IC", "field": "rank_ic", "sortable": True},
                {"name": "ic_positive", "label": "IC dương", "field": "ic_positive", "sortable": True},
                {"name": "excess", "label": "Excess", "field": "excess", "sortable": True},
                {"name": "sharpe", "label": "Sharpe", "field": "sharpe", "sortable": True},
                {"name": "drawdown", "label": "Max DD", "field": "drawdown", "sortable": True},
                {"name": "turnover", "label": "Turnover", "field": "turnover", "sortable": True},
                {"name": "gate", "label": "Qua gate", "field": "gate", "sortable": True},
                {"name": "error", "label": "Lý do bị loại", "field": "error"},
            ],
            rows=[],
            row_key="model",
            pagination=12,
        ).classes("w-full").props("flat bordered dense")
        refs["log"] = ui.textarea(value="").props("readonly autogrow").classes("w-full")

    def render_model() -> None:
        lab = load_model_lab_state(config.data_root)
        grade, champion = model_lab_grade(lab)
        summary = lab.get("summary") if isinstance(lab.get("summary"), Mapping) else {}
        walk = summary.get("walk_forward") if isinstance(summary.get("walk_forward"), Mapping) else {}
        published = bool(summary.get("forward_watchlist_published"))
        refs["grade"].set_text(grade)
        refs["champion"].set_text(f"Champion: {champion}")
        refs["folds"].set_text(f"Fold: {walk.get('fold_count') or '—'}")
        refs["watchlist"].set_text(f"Watchlist: {'ĐƯỢC PHÉP' if published else 'BỊ CHẶN'}")
        refs["model_message"].set_text(
            f"{lab.get('status')} · {lab.get('phase')} · {lab.get('message')}"
            + (f" · {lab.get('error')}" if lab.get("error") else "")
        )
        refs["table"].rows = compact_leaderboard(
            lab.get("leaderboard") if isinstance(lab.get("leaderboard"), list) else []
        )
        refs["table"].update()
        refs["model_stage"].set_text(f"Model Lab: {lab.get('status')} · {lab.get('phase')}")
        refs["output_stage"].set_text(
            f"Output: {lab.get('artifacts_dir') or lab.get('run_dir') or '—'}"
        )

    async def launch(job_id: str, steps: Sequence[PipelineStep]) -> None:
        await asyncio.to_thread(
            execute_job,
            store=jobs,
            job_id=job_id,
            config=config,
            steps=tuple(steps),
        )

    def create_model_job(*, force: bool, handoff: Mapping[str, object]) -> str:
        source = Path(str(handoff["research_input_path"])).resolve()
        signal_date = str(handoff["research_input_signal_date"])
        run_id = datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
        output = config.data_root / "model-lab-live" / "runs" / run_id
        command = [
            sys.executable, "-m", "he_thong_dinh_luong.model_lab_job",
            "--repo-root", str(config.repo_root),
            "--data-root", str(config.data_root),
            "--input-zip", str(source),
            "--output-dir", str(output),
            "--models", ",".join(DEFAULT_MODELS),
            "--evaluation-months", "24",
            "--top-k", "10",
        ]
        if force:
            command.append("--no-reuse")
        log_path = config.logs_dir / f"model-lab-{run_id}.log"
        job_id = jobs.create_job(
            kind="model_lab",
            output_dir=output,
            log_path=log_path,
            parameters={
                "force": force,
                "integrated": True,
                "research_input": str(source),
                "research_input_sha256": handoff["research_input_sha256"],
                "research_input_signal_date": signal_date,
                "research_scope": handoff["research_scope"],
            },
        )
        refs["input_stage"].set_text(
            f"Research input: {signal_date} · {handoff['research_scope']}"
        )
        asyncio.create_task(launch(job_id, (PipelineStep("model_lab_oos", tuple(command)),)))
        return job_id

    async def start() -> None:
        if jobs.active() is not None:
            ui.notify("Đang có job chạy; không tạo job trùng.", type="warning")
            return
        run_id = datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
        output = config.data_root / f"anytime-web-{run_id}"
        command = (
            sys.executable, "-m", "he_thong_dinh_luong.anytime_pipeline",
            "--repo-root", str(config.repo_root),
            "--data-root", str(config.data_root),
            "--output-dir", str(output),
            "--mode", str(refs["mode"].value),
            "--secondary-source", "vci",
            "--crosscheck-sample-size", "20",
            "--initial-capital-vnd", "1000000000",
        )
        log_path = config.logs_dir / f"{output.name}.log"
        job_id = jobs.create_job(
            kind="terminal_refresh",
            output_dir=output,
            log_path=log_path,
            parameters={"mode": refs["mode"].value, "integrated": True},
        )
        state["workflow"] = {
            "market_job": job_id,
            "model_job": None,
            "run_models": bool(refs["models"].value),
            "force": bool(refs["force"].value),
        }
        refs["market_stage"].set_text("Dữ liệu: đang chạy")
        refs["input_stage"].set_text("Research input: chờ handoff")
        refs["model_stage"].set_text("Model Lab: chờ dữ liệu")
        asyncio.create_task(launch(job_id, (PipelineStep("market_prediction_allocation_paper", command),)))
        ui.notify("Workflow đã bắt đầu; mọi kết quả cập nhật tại trang chính.", type="positive")

    def tick() -> None:
        active = jobs.active()
        refs["run"].set_enabled(active is None)
        if active:
            refs["progress"].value = 0.35 if active.get("kind") == "terminal_refresh" else 0.75
            refs["progress"].update()
            if active.get("kind") == "model_lab":
                render_model()
            refs["summary"].set_text(
                f"{active['kind']} · {active['stage']} · job {str(active['id'])[:8]}"
            )
            return
        refs["progress"].value = 0.0
        refs["progress"].update()
        recent = jobs.recent(10)
        handled = state.get("handled") if isinstance(state.get("handled"), set) else set()
        workflow = state.get("workflow") if isinstance(state.get("workflow"), Mapping) else {}
        for job in reversed(recent):
            job_id = str(job.get("id") or "")
            if not job_id or job_id in handled or job.get("status") not in TERMINAL:
                continue
            handled.add(job_id)
            state["handled"] = handled
            refs["log"].value = read_log_tail(Path(str(job["log_path"])), 500)
            refs["log"].update()
            if job.get("kind") == "terminal_refresh" and job_id == workflow.get("market_job"):
                refs["market_stage"].set_text(f"Dữ liệu: {job.get('status')}")
                if job.get("status") == "SUCCESS" and workflow.get("run_models"):
                    try:
                        handoff = load_handoff(Path(str(job["output_dir"])))
                        model_job = create_model_job(
                            force=bool(workflow.get("force")),
                            handoff=handoff,
                        )
                        updated = dict(workflow)
                        updated["model_job"] = model_job
                        state["workflow"] = updated
                        refs["model_stage"].set_text("Model Lab: đang chạy đúng research input")
                        return
                    except Exception as exc:
                        refs["input_stage"].set_text(f"Research input: BLOCKED · {type(exc).__name__}")
                        refs["model_stage"].set_text("Model Lab: bị chặn do handoff không hợp lệ")
                        ui.notify(str(exc), type="negative")
            elif job.get("kind") == "model_lab" and job_id == workflow.get("model_job"):
                render_model()
                state["workflow"] = None
        latest = recent[0] if recent else None
        if latest:
            refs["summary"].set_text(
                f"Job gần nhất: {latest['status']} · {latest['kind']} · exit={latest['return_code']}"
            )

    refs["run"].on("click", start)
    refs["details"].on("click", dialog.open)
    render_model()
    ui.timer(1.0, tick)
    ui.timer(
        0.5,
        lambda: ui.run_javascript(
            "document.querySelectorAll('button').forEach(b=>{if(b.innerText.includes('CẬP NHẬT & PHÂN TÍCH')){const c=b.closest('.q-card');if(c)c.style.display='none';}});"
        ),
        once=True,
    )


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
            "version": "8",
            "nicegui_version": NICEGUI_VERSION,
            "model_lab_integrated": True,
            "exact_research_handoff": True,
            "degenerate_score_gate": True,
            "no_unapproved_forward_watchlist": True,
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
