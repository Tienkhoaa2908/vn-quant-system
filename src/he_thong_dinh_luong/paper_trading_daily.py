"""Ghi nhan paper-trading OOS song tu output EOD va replay bang engine Moc 3."""
from __future__ import annotations

import argparse
import csv
from dataclasses import fields
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import shutil
from typing import Iterable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .mo_phong import cau_hinh_mo_phong, chay_mo_phong
from .mo_phong.mo_hinh import (
    CO_SO_GIA_CHUA_XAC_NHAN,
    thanh_gia,
    ty_trong_muc_tieu,
)

SCHEMA_VERSION = "paper_trading_daily_v1"
PUBLICATION_FILE = "du_lieu_gia_mo_dong_khoi_luong.csv"
SIGNAL_FILE = "paper_portfolio.csv"
DAILY_MANIFEST_FILE = "manifest.json"
SIGNAL_FIELDS = (
    "signal_date", "symbol", "champion_model", "rank",
    "target_weight_pct", "status", "source_zip_sha256",
)


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _csv_bytes(rows: Iterable[Mapping[str, object]], fieldnames: Sequence[str]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return stream.getvalue().encode("utf-8")


def _read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(StringIO(text))]


def _decimal_text(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return ""
    return value


def _dataclass_rows(items: Iterable[object], rename: Mapping[str, str] | None = None) -> tuple[list[dict[str, object]], tuple[str, ...]]:
    values = list(items)
    if not values:
        return [], ()
    rename = dict(rename or {})
    source_fields = tuple(field.name for field in fields(values[0]))
    output_fields = tuple(rename.get(name, name) for name in source_fields)
    rows: list[dict[str, object]] = []
    for item in values:
        rows.append({
            rename.get(name, name): _decimal_text(getattr(item, name))
            for name in source_fields
        })
    return rows, output_fields


def _load_daily_signal(path: Path) -> tuple[list[dict[str, str]], dict[str, object], str]:
    if not path.is_file():
        raise ValueError("DAILY_QUANT_OUTPUT_NOT_FOUND")
    zip_sha = _sha_file(path)
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        if SIGNAL_FILE not in names or DAILY_MANIFEST_FILE not in names:
            raise ValueError("DAILY_QUANT_OUTPUT_SCHEMA_INVALID")
        signal_payload = archive.read(SIGNAL_FILE)
        manifest = json.loads(archive.read(DAILY_MANIFEST_FILE).decode("utf-8-sig"))
    expected = (
        manifest.get("files", {}).get(SIGNAL_FILE, {}).get("sha256")
        if isinstance(manifest, dict) else None
    )
    if expected != _sha_bytes(signal_payload):
        raise ValueError("DAILY_QUANT_OUTPUT_HASH_MISMATCH:paper_portfolio.csv")
    if manifest.get("status") != "SUCCESS":
        raise ValueError("DAILY_QUANT_OUTPUT_NOT_SUCCESS")
    rows = _read_csv_bytes(signal_payload)
    if not rows:
        raise ValueError("PAPER_PORTFOLIO_EMPTY")
    dates = {row.get("signal_date", "").strip() for row in rows}
    if len(dates) != 1 or "" in dates:
        raise ValueError("PAPER_PORTFOLIO_SIGNAL_DATE_INVALID")
    seen: set[str] = set()
    total = Decimal("0")
    normalized: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        if not symbol or symbol in seen:
            raise ValueError("PAPER_PORTFOLIO_SYMBOL_INVALID_OR_DUPLICATE")
        seen.add(symbol)
        weight = Decimal(row.get("target_weight_pct", "").strip())
        if weight < 0 or weight > 100:
            raise ValueError("PAPER_PORTFOLIO_WEIGHT_INVALID")
        total += weight
        normalized.append({
            "signal_date": next(iter(dates)),
            "symbol": symbol,
            "champion_model": row.get("champion_model", "").strip(),
            "rank": row.get("rank", "").strip(),
            "target_weight_pct": str(weight),
            "status": row.get("status", "").strip(),
            "source_zip_sha256": zip_sha,
        })
    if total > 100:
        raise ValueError("PAPER_PORTFOLIO_TOTAL_WEIGHT_EXCEEDS_100")
    return sorted(normalized, key=lambda row: (int(row["rank"] or "999999"), row["symbol"])), manifest, zip_sha


def _signal_payload(rows: Sequence[Mapping[str, object]]) -> bytes:
    return _csv_bytes(rows, SIGNAL_FIELDS)


def _record_signal(state_dir: Path, rows: list[dict[str, str]]) -> Path:
    signal_dir = state_dir / "signals"
    signal_dir.mkdir(parents=True, exist_ok=True)
    signal_date = rows[0]["signal_date"]
    payload = _signal_payload(rows)
    digest = _sha_bytes(payload)
    existing = sorted(signal_dir.glob(f"{signal_date}_*.csv"))
    for path in existing:
        if path.read_bytes() == payload:
            return path
        raise ValueError(f"PAPER_SIGNAL_CONFLICT:{signal_date}")
    path = signal_dir / f"{signal_date}_{digest[:12]}.csv"
    path.write_bytes(payload)
    return path


def _load_all_signals(state_dir: Path) -> tuple[list[dict[str, str]], str]:
    files = sorted((state_dir / "signals").glob("*.csv"))
    if not files:
        raise ValueError("PAPER_SIGNAL_STORE_EMPTY")
    rows: list[dict[str, str]] = []
    digest = sha256()
    seen: set[tuple[str, str]] = set()
    for path in files:
        payload = path.read_bytes()
        digest.update(path.name.encode("utf-8"))
        digest.update(payload)
        for row in _read_csv_bytes(payload):
            key = (row.get("signal_date", ""), row.get("symbol", ""))
            if key in seen:
                raise ValueError(f"PAPER_SIGNAL_DUPLICATE:{key[0]}:{key[1]}")
            seen.add(key)
            rows.append(row)
    return sorted(rows, key=lambda row: (row["signal_date"], row["symbol"])), digest.hexdigest()


def _read_publication(publication_dir: Path, symbols: set[str], first_signal: date) -> tuple[list[thanh_gia], date, str]:
    path = publication_dir / PUBLICATION_FILE
    if not path.is_file():
        raise ValueError("UPDATED_PUBLICATION_NOT_FOUND")
    rows: list[thanh_gia] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("UPDATED_PUBLICATION_SCHEMA_INVALID")
        for raw in reader:
            symbol = raw["ma"].strip().upper()
            if symbol not in symbols:
                continue
            day = date.fromisoformat(raw["ngay"].strip())
            if day < first_signal:
                continue
            open_text = raw["gia_mo_cua"].strip()
            close_text = raw["gia_dong_cua"].strip()
            if not open_text or not close_text:
                raise ValueError(f"PAPER_PRICE_MISSING:{symbol}:{day}")
            volume_text = raw["khoi_luong"].strip()
            volume = int(Decimal(volume_text)) if volume_text else None
            rows.append(thanh_gia(
                ma=symbol,
                ngay=day,
                gia_mo_cua=Decimal(open_text),
                gia_dong_cua=Decimal(close_text),
                khoi_luong=volume,
                thuoc_tap_co_phieu=True,
                dat_thanh_khoan=True,
            ))
    if not rows:
        raise ValueError("PAPER_PRICE_ROWS_EMPTY")
    latest = max(row.ngay for row in rows)
    signal_dates = {row.ngay for row in rows}
    if first_signal not in signal_dates:
        raise ValueError(f"PAPER_SIGNAL_DATE_NOT_IN_PUBLICATION:{first_signal}")
    return sorted(rows, key=lambda row: (row.ngay, row.ma)), latest, _sha_file(path)


def _targets(signal_rows: Sequence[Mapping[str, str]]) -> list[ty_trong_muc_tieu]:
    output: list[ty_trong_muc_tieu] = []
    totals: dict[date, Decimal] = {}
    for row in signal_rows:
        day = date.fromisoformat(row["signal_date"])
        weight = Decimal(row["target_weight_pct"]) / Decimal("100")
        totals[day] = totals.get(day, Decimal("0")) + weight
        output.append(ty_trong_muc_tieu(
            ngay_tin_hieu=day,
            ma=row["symbol"],
            ty_trong=weight,
            ten_chien_luoc=f"paper_{row.get('champion_model') or 'unknown'}",
        ))
    if any(total > 1 for total in totals.values()):
        raise ValueError("PAPER_TARGET_TOTAL_EXCEEDS_ONE")
    return sorted(output, key=lambda row: (row.ngay_tin_hieu, row.ma))


def _config(
    *,
    initial_capital_vnd: int,
    buy_fee_bps: Decimal,
    sell_fee_bps: Decimal,
    sell_tax_bps: Decimal,
    slippage_bps: Decimal,
    lot_size: int,
) -> cau_hinh_mo_phong:
    if initial_capital_vnd <= 0 or initial_capital_vnd % 1000 != 0:
        raise ValueError("INITIAL_CAPITAL_VND_MUST_BE_POSITIVE_MULTIPLE_OF_1000")
    return cau_hinh_mo_phong(
        von_ban_dau=Decimal(initial_capital_vnd) / Decimal("1000"),
        phi_mua_bps=buy_fee_bps,
        phi_ban_bps=sell_fee_bps,
        thue_ban_bps=sell_tax_bps,
        truot_gia_bps=slippage_bps,
        kich_thuoc_lo=lot_size,
        so_phien_moi_nam=252,
        lai_suat_phi_rui_ro=Decimal("0"),
        che_do_ma_khong_xuat_hien="muc_tieu_bang_0",
        cho_phep_ban_le_khi_dong_vi_the=True,
        co_so_gia=CO_SO_GIA_CHUA_XAC_NHAN,
        don_vi_gia="nghin_dong",
        don_vi_tien="nghin_dong",
    )


def _max_drawdown(nav_values: Sequence[Decimal]) -> Decimal:
    if not nav_values:
        return Decimal("0")
    peak = nav_values[0]
    worst = Decimal("0")
    for value in nav_values:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = value / peak - Decimal("1")
            if drawdown < worst:
                worst = drawdown
    return worst


def _order_rows(result: object, latest_market_date: date) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for order in result.lenh:
        status = order.trang_thai
        reason = order.ly_do_tu_choi_hoac_het_han or ""
        if order.ngay_thuc_thi is None and order.ngay_tin_hieu == latest_market_date:
            status = "PENDING_NEXT_SESSION"
            reason = ""
        rows.append({
            "order_id": order.ma_lenh,
            "signal_date": order.ngay_tin_hieu.isoformat(),
            "execution_date": order.ngay_thuc_thi.isoformat() if order.ngay_thuc_thi else "",
            "symbol": order.ma,
            "side": order.chieu,
            "requested_quantity": str(order.so_luong_yeu_cau),
            "quantity": str(order.so_luong),
            "status": status,
            "reason": reason,
            "reduced_quantity": str(order.so_luong_bi_giam),
            "reduction_reason": order.ly_do_giam or "",
        })
    return rows


def _write_snapshot(
    *,
    state_dir: Path,
    snapshot_dir: Path,
    result: object,
    signal_rows: list[dict[str, str]],
    signal_store_digest: str,
    daily_zip_sha: str,
    publication_sha: str,
    latest_market_date: date,
    config: cau_hinh_mo_phong,
) -> dict[str, object]:
    if snapshot_dir.exists():
        manifest_path = snapshot_dir / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return dict(manifest.get("result", {}))
        raise FileExistsError("PAPER_SNAPSHOT_EXISTS_WITHOUT_MANIFEST")
    staging = snapshot_dir.with_name(snapshot_dir.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    signal_fields = tuple(SIGNAL_FIELDS)
    (staging / "signals.csv").write_bytes(_csv_bytes(signal_rows, signal_fields))

    order_fields = (
        "order_id", "signal_date", "execution_date", "symbol", "side",
        "requested_quantity", "quantity", "status", "reason",
        "reduced_quantity", "reduction_reason",
    )
    orders = _order_rows(result, latest_market_date)
    (staging / "orders.csv").write_bytes(_csv_bytes(orders, order_fields))

    fill_rows, fill_fields = _dataclass_rows(result.khop_lenh, {
        "ma_lenh": "order_id", "ma": "symbol", "ngay_khop": "fill_date",
        "chieu": "side", "so_luong": "quantity",
        "gia_mo_cua": "open_price_thousand_vnd",
        "gia_khop": "fill_price_thousand_vnd",
        "gia_tri_giao_dich": "trade_value_thousand_vnd",
        "phi": "fee_thousand_vnd", "thue": "tax_thousand_vnd",
        "chi_phi_truot_gia": "slippage_cost_thousand_vnd",
        "so_luong_yeu_cau": "requested_quantity",
        "so_luong_bi_giam": "reduced_quantity",
        "ly_do_giam": "reduction_reason",
    })
    (staging / "fills.csv").write_bytes(_csv_bytes(fill_rows, fill_fields or ("order_id",)))

    position_rows, position_fields = _dataclass_rows(result.vi_the_hang_ngay, {
        "ngay": "date", "ma": "symbol", "so_luong": "quantity",
        "gia_von": "average_cost_thousand_vnd",
        "gia_dong_cua": "close_price_thousand_vnd",
        "gia_tri_thi_truong": "market_value_thousand_vnd",
        "lai_lo_chua_thuc_hien": "unrealized_pnl_thousand_vnd",
    })
    (staging / "positions_daily.csv").write_bytes(_csv_bytes(position_rows, position_fields or ("date",)))

    nav_rows, nav_fields = _dataclass_rows(result.nav, {
        "ngay": "date", "nav": "nav_thousand_vnd",
        "loi_nhuan_phien": "session_return", "tien_mat": "cash_thousand_vnd",
        "ty_trong_tien_mat": "cash_weight",
    })
    (staging / "nav.csv").write_bytes(_csv_bytes(nav_rows, nav_fields or ("date",)))

    ledger_rows, ledger_fields = _dataclass_rows(result.so_cai, {"ngay": "date"})
    (staging / "ledger.csv").write_bytes(_csv_bytes(ledger_rows, ledger_fields or ("date",)))

    nav_values = [row.nav for row in result.nav]
    last_nav = nav_values[-1]
    average_nav = sum(nav_values, Decimal("0")) / Decimal(len(nav_values))
    traded = sum((fill.gia_tri_giao_dich for fill in result.khop_lenh), Decimal("0"))
    last_ledger = result.so_cai[-1]
    pending = sum(row["status"] == "PENDING_NEXT_SESSION" for row in orders)
    latest_positions = [row for row in result.vi_the_hang_ngay if row.ngay == latest_market_date]
    metrics = {
        "schema_version": SCHEMA_VERSION,
        "status": "PENDING_FIRST_EXECUTION" if not result.khop_lenh else "ACTIVE",
        "latest_market_date": latest_market_date.isoformat(),
        "signal_date_count": len({row["signal_date"] for row in signal_rows}),
        "session_count": len(result.nav),
        "fill_count": len(result.khop_lenh),
        "pending_order_count": pending,
        "current_position_count": len(latest_positions),
        "initial_capital_vnd": int(config.von_ban_dau * Decimal("1000")),
        "latest_nav_vnd": str(last_nav * Decimal("1000")),
        "total_return": str(last_nav / config.von_ban_dau - Decimal("1")),
        "max_drawdown": str(_max_drawdown(nav_values)),
        "turnover_to_average_nav": str(traded / average_nav if average_nav else Decimal("0")),
        "cash_weight": str(result.nav[-1].ty_trong_tien_mat or Decimal("0")),
        "realized_pnl_vnd": str(last_ledger.lai_lo_da_thuc_hien_luy_ke * Decimal("1000")),
        "unrealized_pnl_vnd": str(last_ledger.lai_lo_chua_thuc_hien * Decimal("1000")),
        "fees_vnd": str((last_ledger.phi_mua_luy_ke + last_ledger.phi_ban_luy_ke) * Decimal("1000")),
        "sell_tax_vnd": str(last_ledger.thue_ban_luy_ke * Decimal("1000")),
        "technical_validation_only": True,
        "research_eligible": False,
        "corporate_actions_applied": False,
    }
    (staging / "metrics.json").write_bytes(_json_bytes(metrics))

    summary = "\n".join([
        f"Paper status: {metrics['status']}",
        f"Latest market date: {latest_market_date}",
        f"Signal dates: {metrics['signal_date_count']}",
        f"Sessions observed: {metrics['session_count']}",
        f"Fills: {metrics['fill_count']}",
        f"Pending orders: {metrics['pending_order_count']}",
        f"Current positions: {metrics['current_position_count']}",
        f"Initial capital VND: {metrics['initial_capital_vnd']}",
        f"Latest NAV VND: {metrics['latest_nav_vnd']}",
        f"Total return: {metrics['total_return']}",
        f"Max drawdown: {metrics['max_drawdown']}",
        f"Cash weight: {metrics['cash_weight']}",
        "Execution: signal after close T, fill at open of exact next available market session.",
        "Use: paper trading only; no live order was sent.",
        "Research eligible: false",
        "",
    ])
    (staging / "paper_status.txt").write_text(summary, encoding="utf-8")

    output_names = (
        "signals.csv", "orders.csv", "fills.csv", "positions_daily.csv",
        "nav.csv", "ledger.csv", "metrics.json", "paper_status.txt",
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "latest_market_date": latest_market_date.isoformat(),
        "signal_store_digest": signal_store_digest,
        "inputs": {
            "daily_quant_output_sha256": daily_zip_sha,
            "updated_publication_sha256": publication_sha,
        },
        "configuration": config.thanh_tu_dien(),
        "technical_validation_only": True,
        "research_eligible": False,
        "files": {
            name: {
                "sha256": _sha_file(staging / name),
                "size": (staging / name).stat().st_size,
            }
            for name in output_names
        },
        "result": {
            "status": "SUCCESS",
            "paper_status": metrics["status"],
            "latest_market_date": latest_market_date.isoformat(),
            "fill_count": metrics["fill_count"],
            "pending_order_count": metrics["pending_order_count"],
            "latest_nav_vnd": metrics["latest_nav_vnd"],
            "snapshot_dir": str(snapshot_dir),
        },
    }
    (staging / "manifest.json").write_bytes(_json_bytes(manifest))
    with ZipFile(staging / "paper_state.zip", "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted((*output_names, "manifest.json")):
            archive.write(staging / name, arcname=name)
    snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(snapshot_dir)
    (state_dir / "LATEST.txt").write_text(str(snapshot_dir.resolve()) + "\n", encoding="utf-8")
    return dict(manifest["result"])


def run(
    *,
    daily_output: Path,
    publication_dir: Path,
    state_dir: Path,
    initial_capital_vnd: int = 1_000_000_000,
    buy_fee_bps: Decimal = Decimal("15"),
    sell_fee_bps: Decimal = Decimal("15"),
    sell_tax_bps: Decimal = Decimal("100"),
    slippage_bps: Decimal = Decimal("10"),
    lot_size: int = 100,
) -> dict[str, object]:
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    new_signal, _, daily_zip_sha = _load_daily_signal(Path(daily_output))
    _record_signal(state_dir, new_signal)
    signal_rows, signal_store_digest = _load_all_signals(state_dir)
    signal_dates = sorted({date.fromisoformat(row["signal_date"]) for row in signal_rows})
    symbols = {row["symbol"] for row in signal_rows}
    prices, latest_market_date, publication_sha = _read_publication(
        Path(publication_dir), symbols, signal_dates[0]
    )
    if signal_dates[-1] > latest_market_date:
        raise ValueError("PAPER_SIGNAL_AFTER_LATEST_MARKET_DATE")
    config = _config(
        initial_capital_vnd=initial_capital_vnd,
        buy_fee_bps=buy_fee_bps,
        sell_fee_bps=sell_fee_bps,
        sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps,
        lot_size=lot_size,
    )
    result = chay_mo_phong(prices, _targets(signal_rows), config)
    snapshot_name = f"{latest_market_date}_{signal_store_digest[:12]}"
    return _write_snapshot(
        state_dir=state_dir,
        snapshot_dir=state_dir / "snapshots" / snapshot_name,
        result=result,
        signal_rows=signal_rows,
        signal_store_digest=signal_store_digest,
        daily_zip_sha=daily_zip_sha,
        publication_sha=publication_sha,
        latest_market_date=latest_market_date,
        config=config,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.paper_trading_daily")
    parser.add_argument("--daily-output", type=Path, required=True)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--initial-capital-vnd", type=int, default=1_000_000_000)
    parser.add_argument("--buy-fee-bps", type=Decimal, default=Decimal("15"))
    parser.add_argument("--sell-fee-bps", type=Decimal, default=Decimal("15"))
    parser.add_argument("--sell-tax-bps", type=Decimal, default=Decimal("100"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("10"))
    parser.add_argument("--lot-size", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(
            daily_output=args.daily_output,
            publication_dir=args.publication_dir,
            state_dir=args.state_dir,
            initial_capital_vnd=args.initial_capital_vnd,
            buy_fee_bps=args.buy_fee_bps,
            sell_fee_bps=args.sell_fee_bps,
            sell_tax_bps=args.sell_tax_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
