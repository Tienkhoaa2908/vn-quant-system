"""NiceGUI page for read-only DNSE portfolio analysis."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from .dnse_portfolio import DnseReadOnlyClient, list_masked_accounts, sync_portfolio

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


def _vnd(value: object) -> str:
    try:
        return f"{float(value):,.0f} ₫"
    except (TypeError, ValueError):
        return "—"


def _pct(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def _columns() -> list[dict[str, str]]:
    labels = {
        "symbol": "Mã", "quantity": "Số lượng", "sellable_quantity": "Có thể bán",
        "cost_price_vnd": "Giá vốn", "market_price_vnd": "Giá hiện tại",
        "market_value_vnd": "Giá trị", "unrealized_pnl_vnd": "Lãi/lỗ",
        "unrealized_pnl_pct": "Lãi/lỗ %", "current_weight_pct": "Tỷ trọng hiện tại %",
        "target_weight_pct": "Tỷ trọng mục tiêu %", "target_gap_vnd": "Khoảng thiếu/thừa",
        "ranking_rank": "Hạng", "ranking_score": "Điểm ranking", "above_ma250": "Trên MA250",
        "trend_score": "Trend health", "rsi14": "RSI14", "macd_histogram": "MACD hist",
        "atr14_pct": "ATR14 %", "volume_ratio20": "Volume/TB20", "return_20": "Return 20",
        "return_60": "Return 60", "drawdown_52week": "Drawdown 52w", "action": "Đánh giá",
    }
    preferred = tuple(labels)
    return [
        {"name": name, "label": labels[name], "field": name, "sortable": True, "align": "left"}
        for name in preferred
    ]


def register_portfolio_page(ui: Any, config: Any) -> None:
    @ui.page("/portfolio-dnse")
    def portfolio_page() -> None:
        ui.colors(primary="#17324d", secondary="#42657f", accent="#0f766e", positive="#177245", negative="#b42318")
        ui.add_css("""
            body { background: #f3f6f9; color: #172b3a; }
            .shell { max-width: 1720px; margin: 0 auto; }
            .metric { min-width: 190px; flex: 1 1 190px; border: 1px solid #dfe7ee; box-shadow: none; }
            .metric-value { font-size: 1.36rem; font-weight: 760; }
            .panel { border: 1px solid #dfe7ee; box-shadow: 0 2px 8px rgba(15,23,42,.05); }
            .section-title { font-size: 1.12rem; font-weight: 760; color: #17324d; }
            .read-only { border-left: 5px solid #0f766e; }
            .warning { border-left: 5px solid #d97706; }
        """)
        state: dict[str, object] = {"accounts": {}, "latest": None}
        refs: dict[str, Any] = {}

        with ui.header().classes("items-center justify-between bg-primary text-white px-6"):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round color=white")
                with ui.column().classes("gap-0"):
                    ui.label("Danh mục DNSE · Read-only Portfolio Intelligence").classes("text-h6")
                    ui.label("Vị thế thật · tiền mặt · chỉ báo đồng nhất · target gap · không đặt lệnh").classes("text-caption")
            ui.badge("READ ONLY", color="accent").props("outline")

        def metric(title: str, key: str) -> None:
            with ui.card().classes("metric"):
                ui.label(title).classes("text-caption text-grey-7")
                refs[key] = ui.label("—").classes("metric-value")

        with ui.column().classes("shell w-full p-5 gap-4"):
            with ui.card().classes("panel read-only w-full"):
                ui.label("Kết nối tài khoản chỉ đọc").classes("section-title")
                ui.label(
                    "Chỉ gọi GET account/balance/positions và market data. Không OTP, không Trading Token, không endpoint đặt/sửa/hủy lệnh."
                ).classes("text-body2 text-grey-8")
                with ui.row().classes("items-end gap-3 flex-wrap"):
                    refs["load_accounts"] = ui.button("TẢI TIỂU KHOẢN", icon="account_balance").props("outline")
                    refs["account"] = ui.select({}, label="Tiểu khoản cổ phiếu đã che").classes("w-72")
                    refs["sync"] = ui.button("ĐỒNG BỘ & PHÂN TÍCH", icon="sync").props("unelevated size=lg")
                    refs["context"] = ui.checkbox("Lấy thêm quote/trade/khối ngoại", value=True)
                    refs["status"] = ui.label("Chưa đồng bộ.").classes("text-body2")

            with ui.row().classes("w-full gap-3 flex-wrap"):
                metric("Tài sản ròng", "nav")
                metric("Giá trị cổ phiếu", "stock")
                metric("Tiền khả dụng", "cash")
                metric("Dư nợ", "debt")
                metric("Lãi/lỗ chưa thực hiện", "pnl")
                metric("Tỷ trọng tiền mặt", "cash_weight")
                metric("Vị thế hiệu dụng", "effective")
                metric("Trend health", "trend")

            with ui.card().classes("panel w-full"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("Danh mục hợp nhất").classes("section-title")
                    refs["as_of"] = ui.label("—").classes("text-caption text-grey-7")
                refs["table"] = ui.table(
                    columns=_columns(), rows=[], row_key="symbol", pagination=25
                ).classes("w-full").props("dense flat bordered")

            with ui.row().classes("w-full gap-4 flex-wrap"):
                with ui.card().classes("panel grow min-w-[560px]"):
                    ui.label("Chẩn đoán danh mục").classes("section-title")
                    refs["diagnostics"] = ui.textarea(value="").props("readonly autogrow").classes("w-full")
                with ui.card().classes("panel warning grow min-w-[420px]"):
                    ui.label("Giới hạn nghiên cứu").classes("section-title")
                    refs["warnings"] = ui.label("—").classes("text-body2")
                    ui.label(
                        "Đề xuất chỉ là target-gap kỹ thuật. Không tự động sinh lệnh bán; sector cap chỉ được enforce sau khi có sector master point-in-time tin cậy."
                    ).classes("text-caption text-grey-7")

        def render(snapshot: Path) -> None:
            summary = _json(snapshot / "portfolio_summary.json")
            rows = _csv(snapshot / "portfolio_analysis.csv")
            refs["nav"].set_text(_vnd(summary.get("net_liquidation_value_vnd")))
            refs["stock"].set_text(_vnd(summary.get("stock_market_value_vnd")))
            refs["cash"].set_text(_vnd(summary.get("available_cash_vnd")))
            refs["debt"].set_text(_vnd(summary.get("total_debt_vnd")))
            refs["pnl"].set_text(_vnd(summary.get("unrealized_pnl_vnd")))
            refs["cash_weight"].set_text(_pct(summary.get("cash_weight")))
            refs["effective"].set_text(f"{float(summary.get('effective_position_count') or 0):.2f}")
            refs["trend"].set_text(_pct(summary.get("weighted_trend_health")))
            refs["as_of"].set_text(f"As of {summary.get('as_of', '—')} · {summary.get('masked_account', '—')}")
            refs["table"].rows = rows
            refs["table"].update()
            outside = sum(1 for row in rows if str(row.get("action", "")).startswith(("NO_ADD", "REVIEW")))
            above = sum(1 for row in rows if str(row.get("above_ma250", "")).lower() == "true")
            refs["diagnostics"].value = "\n".join([
                f"Số vị thế: {summary.get('position_count', 0)}",
                f"Trên MA250: {above}/{len(rows)}",
                f"Ngoài target hoặc cần review: {outside}",
                f"Target coverage: {_pct(summary.get('target_coverage'))}",
                f"Largest position: {_pct(summary.get('largest_position_weight'))}",
                f"Concentration HHI: {float(summary.get('concentration_hhi') or 0):.4f}",
                f"Regime: {summary.get('market_regime', '—')}",
                f"Champion: {summary.get('champion_model', '—')}",
                f"Ranking model: {summary.get('ranking_model', '—')}",
            ])
            refs["diagnostics"].update()
            warnings = summary.get("warnings") if isinstance(summary.get("warnings"), list) else []
            refs["warnings"].set_text(" · ".join(str(value) for value in warnings) or "Không có cảnh báo cấu trúc.")
            state["latest"] = snapshot

        async def load_accounts() -> None:
            refs["load_accounts"].set_enabled(False)
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
                refs["account"].options = options
                refs["account"].value = next(iter(options), None)
                refs["account"].update()
                refs["status"].set_text(f"Đã tải {len(accounts)} tiểu khoản. Số thật không gửi xuống bảng/log.")
                ui.notify("Đã tải tiểu khoản read-only.", type="positive")
            except Exception as exc:
                refs["status"].set_text(f"Lỗi: {type(exc).__name__}: {exc}")
                ui.notify("Không tải được tiểu khoản DNSE.", type="negative", timeout=8000)
            finally:
                refs["load_accounts"].set_enabled(True)

        async def sync() -> None:
            token = str(refs["account"].value or "")
            account_map = state.get("accounts") if isinstance(state.get("accounts"), Mapping) else {}
            account_no = account_map.get(token)
            if not account_no:
                ui.notify("Tải và chọn tiểu khoản trước.", type="warning")
                return
            refs["sync"].set_enabled(False)
            refs["status"].set_text("Đang đọc balance, positions, OHLC và tính chỉ báo...")
            output = (
                config.data_root / "dnse-portfolio-live" / "snapshots"
                / datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
            )
            try:
                result = await asyncio.to_thread(
                    sync_portfolio,
                    data_root=config.data_root,
                    output_dir=output,
                    account_no=str(account_no),
                    sync_local_planner=True,
                    include_market_context=bool(refs["context"].value),
                )
                render(output)
                refs["status"].set_text(
                    f"SUCCESS · {result['position_count']} vị thế · {result['masked_account']} · planner đã cập nhật"
                )
                ui.notify("Đồng bộ danh mục DNSE thành công.", type="positive")
            except Exception as exc:
                refs["status"].set_text(f"FAILED · {type(exc).__name__}: {exc}")
                ui.notify("Đồng bộ danh mục thất bại; không có lệnh giao dịch nào được gửi.", type="negative", timeout=9000)
            finally:
                refs["sync"].set_enabled(True)

        refs["load_accounts"].on("click", load_accounts)
        refs["sync"].on("click", sync)
        latest_file = config.data_root / "dnse-portfolio-live" / "LATEST.txt"
        if latest_file.is_file():
            try:
                latest = Path(latest_file.read_text(encoding="utf-8").strip())
                if latest.is_dir():
                    render(latest)
            except (OSError, ValueError):
                pass
