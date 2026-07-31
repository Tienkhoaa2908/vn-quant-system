"""NiceGUI Model Lab page for multi-model walk-forward research."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from .model_lab_core import DEFAULT_MODELS
from .web_local_core import JobStore, LocalWebConfig, PipelineStep, execute_job, read_log_tail

VN_TZ = timezone(timedelta(hours=7))


def _json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _latest_run(data_root: Path) -> Path | None:
    root = data_root / "model-lab-live" / "runs"
    candidates = [
        path for path in root.glob("*")
        if path.is_dir() and _json(path / "manifest.json").get("status") == "SUCCESS"
    ] if root.is_dir() else []
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _columns() -> list[dict[str, object]]:
    return [
        {"name": "model", "label": "Model", "field": "model", "sortable": True, "align": "left"},
        {"name": "family", "label": "Nhóm", "field": "family", "sortable": True},
        {"name": "status", "label": "Trạng thái", "field": "status", "sortable": True},
        {"name": "mean_rank_ic", "label": "Rank IC", "field": "mean_rank_ic", "sortable": True},
        {"name": "positive_rank_ic_ratio", "label": "IC dương", "field": "positive_rank_ic_ratio", "sortable": True},
        {"name": "relative_total_return", "label": "Excess tích lũy", "field": "relative_total_return", "sortable": True},
        {"name": "sharpe", "label": "Sharpe", "field": "sharpe", "sortable": True},
        {"name": "max_drawdown", "label": "Max DD", "field": "max_drawdown", "sortable": True},
        {"name": "mean_set_turnover", "label": "Turnover", "field": "mean_set_turnover", "sortable": True},
        {"name": "gate_passed", "label": "Qua gate", "field": "gate_passed", "sortable": True},
        {"name": "error", "label": "Lỗi/thiếu dependency", "field": "error"},
    ]


def register_model_lab_page(ui: Any, config: LocalWebConfig, jobs: JobStore) -> None:
    @ui.page("/model-lab")
    def model_lab_page() -> None:
        ui.colors(primary="#0b1f33", secondary="#1d3b55", accent="#0f8b8d", positive="#15803d", negative="#b91c1c", warning="#b45309")
        ui.add_css("""
            body { background:#eef2f6; color:#13283a; font-family:Inter,Segoe UI,Arial,sans-serif; }
            .shell { max-width:1720px; margin:0 auto; }
            .surface { background:white; border:1px solid #dbe4ec; border-radius:12px; box-shadow:0 4px 14px rgba(15,35,55,.05); }
            .metric { min-width:200px; flex:1 1 200px; padding:18px; }
            .metric-value { font-size:1.36rem; font-weight:760; color:#102a43; }
            .section-title { font-size:1.15rem; font-weight:760; color:#102a43; }
            .compact-table .q-table th { background:#f5f8fb; color:#334e68; font-weight:700; }
            .mono textarea { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
        """)
        refs: dict[str, Any] = {}
        state: dict[str, object] = {"last_job": None}

        with ui.header().classes("h-16 items-center justify-between bg-primary text-white px-5"):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round color=white")
                with ui.column().classes("gap-0"):
                    ui.label("VN Quant Model Lab").classes("text-h6")
                    ui.label("Walk-forward · nhiều model · deep learning · backtest sau chi phí · fail-closed").classes("text-caption text-blue-1")
            ui.badge("RESEARCH / PAPER ONLY", color="warning").props("outline")

        def metric(title: str, key: str) -> None:
            with ui.card().classes("surface metric"):
                ui.label(title).classes("text-caption text-grey-7")
                refs[key] = ui.label("—").classes("metric-value")

        with ui.column().classes("shell w-full p-5 gap-4"):
            with ui.card().classes("surface w-full p-4"):
                ui.label("Chạy giải đấu model").classes("section-title")
                ui.label(
                    "Mọi model dùng cùng fold, cùng target, cùng Top-K và cùng chi phí. Ensemble chỉ dùng kết quả các fold đã kết thúc; không nhìn nhãn fold hiện tại."
                ).classes("text-body2 text-grey-7")
                with ui.row().classes("w-full items-end gap-3 flex-wrap mt-2"):
                    labels = {
                        "momentum_baseline": "Momentum baseline",
                        "robust_technical_ensemble_v1": "Robust technical",
                        "ridge_ranker": "Ridge",
                        "hist_gradient_boosting_ranker": "Hist Gradient Boosting",
                        "lightgbm_ranker": "LightGBM Ranker",
                        "xgboost_ranker": "XGBoost Ranker",
                        "torch_pairwise_mlp": "PyTorch Pairwise MLP",
                        "online_rank_ensemble_v1": "Online rank ensemble",
                    }
                    refs["models"] = ui.select(
                        labels,
                        value=list(DEFAULT_MODELS),
                        label="Model tham gia",
                        multiple=True,
                    ).props("outlined use-chips").classes("min-w-[620px] grow")
                    refs["months"] = ui.number("Tháng OOS", value=24, min=18, max=48, step=1).classes("w-36")
                    refs["top_k"] = ui.number("Top K", value=10, min=2, max=30, step=1).classes("w-28")
                    refs["run"] = ui.button("CHẠY MODEL LAB", icon="science").props("unelevated size=lg no-caps color=accent")
                refs["progress"] = ui.linear_progress().props("indeterminate").classes("hidden w-full mt-3")
                refs["status"] = ui.label("Chưa có job Model Lab đang chạy.").classes("text-caption text-grey-7 mt-2")
                ui.label(
                    "Lần đầu uv sẽ tải LightGBM 4.7.0, XGBoost 3.3.0 và PyTorch 2.12.1. Model lỗi hoặc thiếu dependency bị loại riêng; baseline vẫn chạy."
                ).classes("text-caption text-orange-9")

            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric("Phán quyết", "grade")
                metric("Champion nghiên cứu", "champion")
                metric("Số fold OOS", "folds")
                metric("Model chạy thành công", "successful")
                metric("Cho phép vốn thật", "capital")

            with ui.card().classes("surface w-full p-4"):
                ui.label("Kết luận").classes("section-title")
                refs["verdict"] = ui.label("Chưa có kết quả.").classes("text-body1")
                refs["contract"] = ui.label("—").classes("text-body2 text-grey-7")

            with ui.card().classes("surface w-full p-4"):
                ui.label("Leaderboard OOS").classes("section-title")
                refs["leaderboard"] = ui.table(
                    columns=_columns(), rows=[], row_key="model", pagination=20,
                ).classes("w-full compact-table").props("flat bordered dense")

            with ui.card().classes("surface w-full p-4"):
                ui.label("NAV tương đối sau chi phí").classes("section-title")
                refs["nav_chart"] = ui.echart({
                    "tooltip": {"trigger": "axis"},
                    "legend": {"type": "scroll", "data": []},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "scale": True},
                    "dataZoom": [{"type": "inside"}, {"type": "slider"}],
                    "series": [],
                }).classes("w-full h-96")

            with ui.card().classes("surface w-full p-4"):
                with ui.expansion("Log và giới hạn nghiên cứu", icon="terminal").classes("w-full"):
                    refs["log"] = ui.textarea(value="").props("readonly autogrow").classes("w-full mono")
                    refs["limitations"] = ui.label("—").classes("text-body2 text-grey-7")

        def render(run: Path) -> None:
            summary = _json(run / "model_lab_summary.json")
            rows = _csv(run / "model_leaderboard.csv")
            nav_rows = _csv(run / "oos_nav.csv")
            refs["grade"].set_text(str(summary.get("evidence_grade") or "—"))
            refs["champion"].set_text(str(summary.get("research_champion") or "—"))
            walk = summary.get("walk_forward") if isinstance(summary.get("walk_forward"), Mapping) else {}
            refs["folds"].set_text(str(walk.get("fold_count") or "—"))
            success = sum(1 for row in rows if row.get("status") == "SUCCESS")
            refs["successful"].set_text(str(success))
            refs["capital"].set_text("KHÔNG")
            refs["verdict"].set_text(
                f"{summary.get('research_champion', '—')} · {summary.get('champion_reason', '—')} · Forward reference: {summary.get('reference_model_for_forward_watchlist', '—')}"
            )
            backtest = summary.get("backtest_contract") if isinstance(summary.get("backtest_contract"), Mapping) else {}
            refs["contract"].set_text(
                f"Backtest: {backtest.get('type', '—')} · execution engine={backtest.get('execution_engine_used', False)}. {backtest.get('warning', '')}"
            )
            refs["leaderboard"].rows = rows
            refs["leaderboard"].update()
            dates = sorted({row.get("date", "") for row in nav_rows if row.get("date")})
            models = sorted({row.get("model", "") for row in nav_rows if row.get("model")})
            by_key = {(row.get("model", ""), row.get("date", "")): row for row in nav_rows}
            refs["nav_chart"].options["xAxis"]["data"] = dates
            refs["nav_chart"].options["legend"]["data"] = models
            refs["nav_chart"].options["series"] = [
                {
                    "type": "line", "name": model, "showSymbol": False,
                    "data": [float(by_key.get((model, day), {}).get("relative_nav") or 0) for day in dates],
                }
                for model in models
            ]
            refs["nav_chart"].update()
            limitations = summary.get("limitations") if isinstance(summary.get("limitations"), list) else []
            refs["limitations"].set_text(" · ".join(str(value) for value in limitations))

        async def launch(job_id: str, step: PipelineStep) -> None:
            await asyncio.to_thread(execute_job, store=jobs, job_id=job_id, config=config, steps=(step,))

        async def start() -> None:
            input_zip = config.data_root / "prediction_input.zip"
            if not input_zip.is_file():
                ui.notify("Thiếu prediction_input.zip trong data root.", type="negative", timeout=8000)
                return
            selected = [str(value) for value in (refs["models"].value or [])]
            if "momentum_baseline" not in selected:
                ui.notify("Momentum baseline bắt buộc để làm đối chứng.", type="warning")
                return
            run_id = datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
            output = config.data_root / "model-lab-live" / "runs" / run_id
            log_path = config.logs_dir / f"model-lab-{run_id}.log"
            command = (
                "uv", "run", "--python", "3.12",
                "--with", "lightgbm==4.7.0",
                "--with", "xgboost==3.3.0",
                "--with", "torch==2.12.1",
                "python", "-m", "he_thong_dinh_luong.model_lab",
                "--input-zip", str(input_zip),
                "--output-dir", str(output),
                "--models", ",".join(selected),
                "--evaluation-months", str(int(refs["months"].value or 24)),
                "--top-k", str(int(refs["top_k"].value or 10)),
            )
            try:
                job_id = jobs.create_job(
                    kind="model_lab",
                    output_dir=output,
                    log_path=log_path,
                    parameters={"models": selected, "evaluation_months": refs["months"].value, "top_k": refs["top_k"].value},
                )
            except Exception as exc:
                ui.notify(f"Không thể tạo job: {type(exc).__name__}: {exc}", type="negative")
                return
            state["last_job"] = None
            asyncio.create_task(launch(job_id, PipelineStep("walk_forward_multimodel_backtest", command)))
            ui.notify("Model Lab đã bắt đầu. Kết quả sẽ tự cập nhật tại trang này.", type="positive")

        def tick() -> None:
            active = jobs.active()
            is_lab = active is not None and active.get("kind") == "model_lab"
            refs["run"].set_enabled(active is None)
            refs["progress"].set_visibility(bool(is_lab))
            if active:
                refs["status"].set_text(f"{active['kind']} · {active['stage']} · {active['id'][:8]}")
                if is_lab:
                    refs["log"].value = read_log_tail(Path(str(active["log_path"])), 500)
                    refs["log"].update()
                return
            recent = jobs.recent(10)
            latest_job = next((job for job in recent if job.get("kind") == "model_lab"), None)
            if latest_job:
                refs["status"].set_text(f"Model Lab gần nhất: {latest_job['status']} · exit={latest_job['return_code']}")
                refs["log"].value = read_log_tail(Path(str(latest_job["log_path"])), 500)
                refs["log"].update()
                if latest_job["status"] == "SUCCESS" and state.get("last_job") != latest_job["id"]:
                    state["last_job"] = latest_job["id"]
                    output = Path(str(latest_job["output_dir"]))
                    if output.is_dir():
                        render(output)
                        ui.notify("Model Lab hoàn tất; leaderboard đã cập nhật.", type="positive")

        refs["run"].on("click", start)
        latest = _latest_run(config.data_root)
        if latest:
            render(latest)
        ui.timer(1.0, tick)
