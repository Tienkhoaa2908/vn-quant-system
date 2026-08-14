from __future__ import annotations

import csv
from datetime import date
from io import StringIO
import json
from pathlib import Path
import zipfile

from he_thong_dinh_luong import all_history_protocol_v31 as v31
from he_thong_dinh_luong import component_breadth_ablation_v27 as v27


FEATURES = {
    "dong_luong_12_1": 0.10,
    "bien_dong_60": 0.20,
    "suc_manh_tuong_doi_120": 0.30,
    "khoang_cach_ma60": 0.04,
    "khoang_cach_ma120": 0.03,
    "khoang_cach_ma250": -0.02,
    "loi_nhuan_20": 0.01,
    "loi_nhuan_60": 0.02,
    "loi_nhuan_120": 0.03,
    "loi_nhuan_250": 0.04,
    "ty_le_dinh_52_tuan": 0.80,
    "vnindex_tren_ma250": 0.0,
}


def _month_day(index: int) -> date:
    year = 2020 + index // 12
    month = index % 12 + 1
    return date(year, month, 1)


def _row(index: int, symbol: str = "AAA") -> v27.ResearchRow:
    signal_day = _month_day(index)
    return v27.ResearchRow(
        signal_day=signal_day,
        symbol=symbol,
        label_end=date(signal_day.year, signal_day.month, 20),
        stock_return=0.02,
        benchmark_return=0.01,
        relative_return=0.01,
        features=dict(FEATURES),
    )


def _csv_payload(rows: list[dict[str, object]], fields: list[str]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def test_loader_keeps_feature_complete_row_below_ma250_and_ineligible(
    tmp_path: Path,
) -> None:
    feature = {
        "ngay": "2020-01-31",
        "ma": "AAA",
        "hop_le": "true",
        "eligible": "false",
        "gia_tren_ma250": "false",
        **{name: value for name, value in FEATURES.items()},
    }
    label = {
        "ngay": "2020-01-31",
        "ma": "AAA",
        "ngay_ket_thuc_nhan": "2020-02-28",
        "loi_nhuan_co_phieu": "0.02",
        "loi_nhuan_benchmark": "0.01",
        "loi_nhuan_tuong_doi": "0.01",
    }
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "feature_raw.csv",
            _csv_payload([feature], list(feature)),
        )
        archive.writestr("nhan.csv", _csv_payload([label], list(label)))
        archive.writestr("manifest.json", json.dumps({"schema_version": "test"}))

    rows, manifest, coverage = v31._load_all_history_zip(source)

    assert manifest["schema_version"] == "test"
    assert len(rows) == 1
    assert rows[0].symbol == "AAA"
    assert coverage["portfolio_eligible_trainable_row_count"] == 0
    assert coverage["non_portfolio_eligible_trainable_row_count"] == 1
    assert coverage["below_or_not_above_ma250_trainable_row_count"] == 1
    assert coverage["portfolio_eligibility_used_as_training_filter"] is False


def test_pooled_split_uses_all_months_once_in_final_train_or_test() -> None:
    rows = tuple(_row(index) for index in range(22))

    train, validation, test, blocks, summary = v31.build_pooled_seven_month_split(
        rows,
        block_months=7,
        test_slot=7,
        validation_slot=6,
    )

    train_dates = {row.signal_day for row in train}
    validation_dates = {row.signal_day for row in validation}
    test_dates = {row.signal_day for row in test}
    assert len(test_dates) == 3
    assert len(validation_dates) == 3
    assert len(train_dates) == 16
    assert len(train_dates | validation_dates) == 19
    assert len((train_dates | validation_dates) | test_dates) == 22
    assert not (train_dates | validation_dates) & test_dates
    assert summary["complete_block_count"] == 3
    assert summary["remainder_month_count_assigned_to_final_train"] == 1
    assert summary["all_input_months_used_exactly_once_in_final_train_or_test"] is True
    assert any(row["block_number"] == "REMAINDER_TO_FINAL_TRAIN" for row in blocks)


def test_cross_sectional_percentiles_restart_each_month() -> None:
    rows = (
        _row(0, "A"),
        _row(0, "B"),
        _row(1, "A"),
        _row(1, "B"),
    )
    values = (1.0, 2.0, 100.0, 200.0)

    ranked = v31._cross_sectional_percentiles(rows, values)

    assert ranked == [0.0, 1.0, 0.0, 1.0]


def test_primary_fold_audit_never_uses_future_rows() -> None:
    rows = tuple(
        _row(month, symbol)
        for month in range(20)
        for symbol in ("A", "B", "C", "D", "E")
    )
    folds = v27.build_folds(
        rows,
        evaluation_months=20,
        minimum_train_months=12,
        inner_validation_months=1,
    )

    audit = v31._primary_fold_audit(rows, folds)

    assert audit
    assert all(row["future_rows_used_for_fit"] is False for row in audit)
    assert all(row["test_rows_used_for_fit"] is False for row in audit)
    assert all(row["train_last_date"] < row["test_date"] for row in audit)
    assert all(row["validation_last_date"] < row["test_date"] for row in audit)
