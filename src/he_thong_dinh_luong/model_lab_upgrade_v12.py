"""Model Lab v12: forced-exit accounting hotfix for the v11 policy.

V11's selection rule already treated unavailable prior holdings as forced exits,
but its diagnostic replacement counter included the securities bought to replace
those forced exits. V12 corrects the accounting without changing selections,
returns, costs, ranks, the three-replacement policy, or any research gate.

The v12 publisher corrects the already-published v11 period rows. It deliberately
does not monkeypatch ``v11.turnover_capped_periods`` while v11 is running: doing
so would make ``corrected_turnover_capped_periods`` call itself recursively.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v11 as v11

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v12"


def corrected_turnover_capped_periods(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    max_voluntary_replacements: int = v11.MAX_VOLUNTARY_REPLACEMENTS,
    buy_fee_bps: float,
    sell_fee_bps: float,
    sell_tax_bps: float,
    slippage_bps: float,
) -> list[dict[str, object]]:
    """Return v11 periods with forced and voluntary replacements separated."""
    rows = v11.turnover_capped_periods(
        prediction_rows,
        top_k=top_k,
        max_voluntary_replacements=max_voluntary_replacements,
        buy_fee_bps=buy_fee_bps,
        sell_fee_bps=sell_fee_bps,
        sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps,
    )
    previous: set[str] = set()
    for index, row in enumerate(rows):
        selected = {
            symbol
            for symbol in str(row.get("selected_symbols") or "").split("|")
            if symbol
        }
        if index == 0:
            voluntary = 0
        else:
            overlap = len(previous & selected)
            total_replacements = max(0, top_k - overlap)
            forced = int(float(row.get("forced_exit_count", 0) or 0))
            voluntary = max(0, total_replacements - forced)
        row["voluntary_replacement_count"] = voluntary
        row["voluntary_replacement_cap_respected"] = str(
            voluntary <= max_voluntary_replacements
        ).lower()
        previous = selected
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(fields),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def publish_v12_contract(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    periods_path = output / "turnover_capped_reference_periods.csv"
    periods = _read_csv(periods_path)
    corrected = []
    previous: set[str] = set()
    for index, row in enumerate(periods):
        selected = {
            symbol
            for symbol in str(row.get("selected_symbols") or "").split("|")
            if symbol
        }
        top_k = int(float(row.get("top_k", 10) or 10))
        cap = int(float(row.get("max_voluntary_replacements", 3) or 3))
        if index == 0:
            voluntary = 0
        else:
            overlap = len(previous & selected)
            total_replacements = max(0, top_k - overlap)
            forced = int(float(row.get("forced_exit_count", 0) or 0))
            voluntary = max(0, total_replacements - forced)
        row["voluntary_replacement_count"] = str(voluntary)
        row["voluntary_replacement_cap_respected"] = str(
            voluntary <= cap
        ).lower()
        corrected.append(row)
        previous = selected
    if corrected:
        fields = list(corrected[0])
        if "voluntary_replacement_cap_respected" not in fields:
            fields.append("voluntary_replacement_cap_respected")
        _write_csv(periods_path, corrected, fields)

    audit_rows = [
        {
            "signal_date": row.get("signal_date", ""),
            "forced_exit_count": row.get("forced_exit_count", ""),
            "voluntary_replacement_count": row.get(
                "voluntary_replacement_count", ""
            ),
            "max_voluntary_replacements": row.get(
                "max_voluntary_replacements", ""
            ),
            "voluntary_replacement_cap_respected": row.get(
                "voluntary_replacement_cap_respected", "false"
            ),
            "selection_changed_vs_v11": "false",
            "returns_changed_vs_v11": "false",
            "actionable": "false",
        }
        for row in corrected
    ]
    _write_csv(
        output / "turnover_cap_contract_v12.csv",
        audit_rows,
        (
            "signal_date",
            "forced_exit_count",
            "voluntary_replacement_count",
            "max_voluntary_replacements",
            "voluntary_replacement_cap_respected",
            "selection_changed_vs_v11",
            "returns_changed_vs_v11",
            "actionable",
        ),
    )
    all_respected = bool(audit_rows) and all(
        str(row["voluntary_replacement_cap_respected"]).lower() == "true"
        for row in audit_rows
    )

    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    summary["base_upgrade_schema_version"] = v11.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["predictive_upgrade_v12"] = {
        "change": "FORCED_EXIT_ACCOUNTING_ONLY",
        "selection_changed_vs_v11": False,
        "returns_changed_vs_v11": False,
        "voluntary_replacement_cap_respected_all_periods": all_respected,
        "research_gate_relaxed": False,
        "actionable": False,
        "files": ["turnover_cap_contract_v12.csv"],
    }
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    with (output / "model_lab_report.txt").open(
        "a",
        encoding="utf-8",
    ) as stream:
        stream.write("\nMODEL LAB UPGRADE V12\n")
        stream.write(
            "Forced exits are accounted separately from the maximum three "
            "voluntary replacements; selection and returns are unchanged.\n"
        )
        stream.write(
            f"Voluntary replacement cap respected for all periods: "
            f"{str(all_respected).lower()}; actionable=false.\n"
        )
    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "voluntary_replacement_cap_respected_all_periods": all_respected,
        "research_champion": summary.get(
            "research_champion", "NO_MODEL_APPROVED"
        ),
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    """Run v11 unchanged, then correct only the published accounting rows."""
    result = v11.run_model_lab(**kwargs)
    audit = publish_v12_contract(Path(str(kwargs["output_dir"])))
    return {**result, **audit}


def _parser():
    return v11._parser()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_model_lab(
        input_zip=args.input_zip,
        output_dir=args.output_dir,
        models=tuple(
            item.strip()
            for item in args.models.split(",")
            if item.strip()
        ),
        evaluation_months=args.evaluation_months,
        minimum_train_months=args.minimum_train_months,
        inner_validation_months=args.inner_validation_months,
        top_k=args.top_k,
        turnover_buffer=args.turnover_buffer,
        seed=args.seed,
        strict_dependencies=args.strict_dependencies,
        buy_fee_bps=args.buy_fee_bps,
        sell_fee_bps=args.sell_fee_bps,
        sell_tax_bps=args.sell_tax_bps,
        slippage_bps=args.slippage_bps,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "corrected_turnover_capped_periods",
    "publish_v12_contract",
    "run_model_lab",
    "main",
]
