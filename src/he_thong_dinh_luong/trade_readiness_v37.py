"""Integrated trade-readiness gate for the frozen C3/Top-10/cap-3 policy.

V37 does not retrain models. It consumes the latest V36 artifact, future paper
observations and an operational checklist, then emits one capital-stage decision:
DATA_BLOCKED, PAPER_ONLY, or MANUAL_MICRO_LIVE_REVIEW_ELIGIBLE.

The last state is only eligibility for a human capital review. It never grants
live-capital permission or automatic order permission.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
from statistics import fmean
from typing import Mapping, Sequence
import zipfile

SCHEMA_VERSION = "vn_quant_trade_readiness_v37"
REPORT_FILE = "trade_readiness_v37.json"
GATES_FILE = "trade_readiness_gates_v37.csv"
WORKPLAN_FILE = "trade_readiness_workplan_v37.csv"
PAPER_TEMPLATE_FILE = "paper_observations_v37.csv"
OPS_TEMPLATE_FILE = "operational_checklist_v37.json"
EXPECTED_POLICY_ID = "c3-top10-cap3-c32fe6ec8c2fd4ce"
MINIMUM_FUTURE_OBSERVATIONS = 12

OPS_KEYS = (
    "data_freshness_fail_closed",
    "idempotent_daily_run_verified",
    "kill_switch_tested",
    "manual_order_confirmation_required",
    "account_sync_verified",
    "position_reconciliation_verified",
    "stale_signal_rejected",
    "duplicate_order_prevention_tested",
    "no_automatic_live_orders",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _safe_basename(name: str) -> str:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"V37_UNSAFE_ZIP_MEMBER:{name}")
    return path.name


def _load_v36_artifact(path: Path, expected_sha256: str = "") -> dict[str, object]:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"V37_V36_ARTIFACT_NOT_FOUND:{source}")
    actual = _sha256(source)
    if expected_sha256 and actual != expected_sha256:
        raise ValueError(f"V37_V36_SHA256_MISMATCH:{actual}")
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"V37_V36_ZIP_CRC_ERROR:{bad}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = _safe_basename(info.filename)
            if basename in members:
                raise ValueError(f"V37_DUPLICATE_MEMBER:{basename}")
            members[basename] = archive.read(info)
    required = {"analysis_bundle_manifest_v36.json", "integrated_data_ledger_v36.json"}
    missing = required - set(members)
    if missing:
        raise ValueError("V37_V36_REQUIRED_MISSING:" + "|".join(sorted(missing)))
    manifest = json.loads(members["analysis_bundle_manifest_v36.json"].decode("utf-8-sig"))
    if manifest.get("status") != "SUCCESS":
        raise ValueError("V37_V36_MANIFEST_NOT_SUCCESS")
    verified = 0
    for item in manifest.get("files", []):
        basename = _safe_basename(str(item.get("path") or ""))
        payload = members.get(basename)
        if payload is None:
            raise ValueError(f"V37_V36_MANIFEST_MEMBER_MISSING:{basename}")
        if len(payload) != int(item.get("size_bytes", -1)):
            raise ValueError(f"V37_V36_MANIFEST_SIZE_MISMATCH:{basename}")
        if sha256(payload).hexdigest() != str(item.get("sha256") or ""):
            raise ValueError(f"V37_V36_MANIFEST_HASH_MISMATCH:{basename}")
        verified += 1
    report = json.loads(members["integrated_data_ledger_v36.json"].decode("utf-8-sig"))
    if report.get("status") != "SUCCESS":
        raise ValueError("V37_V36_REPORT_NOT_SUCCESS")
    return {
        "path": str(source),
        "sha256": actual,
        "manifest_entry_count": verified,
        "report": report,
    }


def _read_paper(path: Path | None) -> list[dict[str, object]]:
    if path is None or not Path(path).is_file():
        return []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    completed: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        signal = str(row.get("signal_date") or "")[:10]
        label_end = str(row.get("label_end") or "")[:10]
        is_complete = str(row.get("completed") or "").strip().lower() in {"true", "1", "yes"}
        contract_ok = str(row.get("contract_ok") or "").strip().lower() in {"true", "1", "yes"}
        if not signal or signal in seen or not is_complete:
            continue
        seen.add(signal)
        try:
            net_return = float(row.get("net_return") or 0.0)
            benchmark_return = float(row.get("benchmark_return") or 0.0)
            drawdown = float(row.get("drawdown") or 0.0)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (net_return, benchmark_return, drawdown)):
            continue
        completed.append({
            "signal_date": signal,
            "label_end": label_end,
            "contract_ok": contract_ok,
            "net_return": net_return,
            "benchmark_return": benchmark_return,
            "net_excess_return": net_return - benchmark_return,
            "drawdown": drawdown,
        })
    completed.sort(key=lambda row: str(row["signal_date"]))
    return completed


def _read_ops(path: Path | None) -> dict[str, object]:
    if path is None or not Path(path).is_file():
        return {key: False for key in OPS_KEYS}
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, Mapping):
        raise ValueError("V37_OPERATIONAL_CHECKLIST_NOT_OBJECT")
    return {key: value.get(key) is True for key in OPS_KEYS}


def _paper_metrics(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if not rows:
        return {
            "completed_observation_count": 0,
            "mean_net_excess_return": 0.0,
            "positive_net_excess_ratio": 0.0,
            "worst_drawdown": 0.0,
            "contract_violation_count": 0,
        }
    excess = [float(row["net_excess_return"]) for row in rows]
    return {
        "completed_observation_count": len(rows),
        "first_signal_date": rows[0]["signal_date"],
        "last_signal_date": rows[-1]["signal_date"],
        "mean_net_excess_return": fmean(excess),
        "positive_net_excess_ratio": sum(value > 0.0 for value in excess) / len(excess),
        "worst_drawdown": min(float(row["drawdown"]) for row in rows),
        "contract_violation_count": sum(not bool(row["contract_ok"]) for row in rows),
    }


def _gate(name: str, passed: bool, blocker: str, weight: float) -> dict[str, object]:
    return {"gate": name, "passed": passed, "blocker": "" if passed else blocker, "weight": weight}


def evaluate_trade_readiness(
    v36_report: Mapping[str, object],
    paper_rows: Sequence[Mapping[str, object]],
    ops: Mapping[str, object],
) -> dict[str, object]:
    data_assurance = dict(v36_report.get("data_assurance") or {})
    selection = dict(v36_report.get("selection_lineage") or {})
    automatic = dict(v36_report.get("automatic_reference_preparation") or {})
    policy_pass = (
        str(v36_report.get("policy_id") or "") == EXPECTED_POLICY_ID
        and v36_report.get("frozen_policy_unchanged") is True
    )
    selection_pass = selection.get("exact_match") is True and int(selection.get("period_count") or 0) == 51
    exact_ledger_pass = (
        v36_report.get("ledger_status") == "SUCCESS"
        and v36_report.get("exact_cash_ledger_pnl_computed") is True
    )
    benchmark_pass = v36_report.get("exact_vnindex_comparison_computed") is True
    data_pass = data_assurance.get("valid") is True
    paper = _paper_metrics(paper_rows)
    observation_count = int(paper["completed_observation_count"])
    paper_count_pass = observation_count >= MINIMUM_FUTURE_OBSERVATIONS
    paper_quality_pass = (
        paper_count_pass
        and int(paper["contract_violation_count"]) == 0
        and float(paper["mean_net_excess_return"]) > 0.0
        and float(paper["positive_net_excess_ratio"]) >= 0.55
        and float(paper["worst_drawdown"]) >= -0.25
    )
    ops_pass = all(ops.get(key) is True for key in OPS_KEYS)
    gates = [
        _gate("FROZEN_MODEL_POLICY", policy_pass, "MODEL_POLICY_NOT_FROZEN", 20.0),
        _gate("SELECTION_LINEAGE_51_OF_51", selection_pass, "SELECTION_LINEAGE_MISMATCH", 10.0),
        _gate("AUTHORITATIVE_DATA_ASSURANCE", data_pass, "AUTHORITATIVE_DATA_PACK_INCOMPLETE", 10.0),
        _gate("EXACT_CASH_LEDGER", exact_ledger_pass, "EXACT_LEDGER_NOT_COMPUTED", 20.0),
        _gate("EXACT_VNINDEX_COMPARISON", benchmark_pass, "EXACT_VNINDEX_NOT_COMPUTED", 5.0),
        _gate("FUTURE_HOLDOUT_12_COMPLETE", paper_count_pass, "FUTURE_HOLDOUT_INCOMPLETE", 15.0),
        _gate("FUTURE_HOLDOUT_QUALITY", paper_quality_pass, "FUTURE_HOLDOUT_QUALITY_FAIL", 10.0),
        _gate("OPERATIONAL_CONTROLS", ops_pass, "OPERATIONAL_CONTROLS_INCOMPLETE", 10.0),
    ]
    score = sum(float(row["weight"]) for row in gates if row["passed"])
    if not policy_pass or not selection_pass:
        stage = "NO_GO_MODEL"
        next_action = "FIX_POLICY_OR_SELECTION_LINEAGE"
    elif not data_pass or not exact_ledger_pass or not benchmark_pass:
        stage = "DATA_BLOCKED"
        next_action = "COMPLETE_AUTHORITATIVE_DATA_PACK_AND_RERUN_V36"
    elif not paper_quality_pass:
        stage = "PAPER_ONLY"
        next_action = "ACCUMULATE_AND_EVALUATE_12_FUTURE_OBSERVATIONS"
    elif not ops_pass:
        stage = "PAPER_ONLY_OPERATIONS"
        next_action = "COMPLETE_OPERATIONAL_DRY_RUNS_AND_CONTROLS"
    else:
        stage = "MANUAL_MICRO_LIVE_REVIEW_ELIGIBLE"
        next_action = "HUMAN_CAPITAL_COMMITTEE_REVIEW_ONLY"
    blockers = [str(row["blocker"]) for row in gates if row["blocker"]]
    workplan = [
        {"priority": 1, "workstream": "REFERENCE_DATA", "status": "PASS" if data_pass else "BLOCKED", "deliverable": "price basis + sector PIT + corporate actions + assurance hash"},
        {"priority": 2, "workstream": "EXACT_LEDGER", "status": "PASS" if exact_ledger_pass and benchmark_pass else "BLOCKED", "deliverable": "Open T+1 cash ledger, base/stress, exact VNINDEX"},
        {"priority": 3, "workstream": "FUTURE_HOLDOUT", "status": f"{observation_count}/{MINIMUM_FUTURE_OBSERVATIONS}", "deliverable": "12 completed monthly observations without backfill"},
        {"priority": 4, "workstream": "OPERATIONS", "status": "PASS" if ops_pass else "BLOCKED", "deliverable": "freshness, idempotency, kill switch, reconciliation, duplicate prevention"},
        {"priority": 5, "workstream": "CAPITAL_REVIEW", "status": "ELIGIBLE" if stage == "MANUAL_MICRO_LIVE_REVIEW_ELIGIBLE" else "NOT_ELIGIBLE", "deliverable": "manual decision; no automatic live orders"},
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "objective": "EVIDENCE_SUFFICIENT_FOR_CONTROLLED_REAL_CAPITAL_REVIEW",
        "policy_id": EXPECTED_POLICY_ID,
        "capital_stage": stage,
        "readiness_score_percent": score,
        "next_action": next_action,
        "gates": gates,
        "blockers": blockers,
        "v36_blockers": list(v36_report.get("blockers") or []),
        "paper_holdout": paper,
        "operational_controls": dict(ops),
        "automatic_reference_preparation": automatic,
        "workplan": workplan,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "manual_micro_live_review_eligible": stage == "MANUAL_MICRO_LIVE_REVIEW_ELIGIBLE",
        "calendar_time_cannot_be_backfilled": True,
    }


def run_v37(
    *,
    v36_artifact_zip: Path,
    output_dir: Path,
    expected_v36_sha256: str = "",
    paper_observations: Path | None = None,
    operational_checklist: Path | None = None,
) -> dict[str, object]:
    out = Path(output_dir).resolve()
    if out.exists():
        raise FileExistsError(f"V37_OUTPUT_EXISTS:{out}")
    out.mkdir(parents=True)
    v36 = _load_v36_artifact(v36_artifact_zip, expected_v36_sha256)
    paper_rows = _read_paper(paper_observations)
    ops = _read_ops(operational_checklist)
    report = evaluate_trade_readiness(v36["report"], paper_rows, ops)
    report["source_v36"] = {
        "path": v36["path"],
        "sha256": v36["sha256"],
        "manifest_entry_count": v36["manifest_entry_count"],
    }
    _write_json(out / REPORT_FILE, report)
    _write_csv(out / GATES_FILE, report["gates"], ("gate", "passed", "blocker", "weight"))
    _write_csv(out / WORKPLAN_FILE, report["workplan"], ("priority", "workstream", "status", "deliverable"))
    _write_csv(
        out / PAPER_TEMPLATE_FILE,
        paper_rows,
        ("signal_date", "label_end", "completed", "contract_ok", "net_return", "benchmark_return", "drawdown"),
    )
    if not paper_rows:
        _write_csv(
            out / PAPER_TEMPLATE_FILE,
            [],
            ("signal_date", "label_end", "completed", "contract_ok", "net_return", "benchmark_return", "drawdown"),
        )
    _write_json(out / OPS_TEMPLATE_FILE, {key: bool(ops.get(key)) for key in OPS_KEYS})
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Integrated trade-readiness gate V37")
    parser.add_argument("--v36-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v36-sha256", default="")
    parser.add_argument("--paper-observations", type=Path)
    parser.add_argument("--operational-checklist", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_v37(
        v36_artifact_zip=args.v36_artifact_zip,
        output_dir=args.output_dir,
        expected_v36_sha256=args.expected_v36_sha256,
        paper_observations=args.paper_observations,
        operational_checklist=args.operational_checklist,
    )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
