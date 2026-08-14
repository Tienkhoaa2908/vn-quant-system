"""Build a reproducible handoff bundle for independent AI review.

The bundle contains a source snapshot at one exact Git commit, selected model
and research artifacts, data lineage, a reviewer prompt, and cryptographic
hashes. It deliberately excludes credentials, broker account exports, and the
full historical SQLite store unless a caller explicitly handles those outside
this tool.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from typing import Iterable, Mapping, Sequence
import zipfile

SCHEMA_VERSION = "ai_review_bundle_v1"
REPORT_FILE = "ai_review_bundle_v1.json"
BUNDLE_ZIP_NAME = "UPLOAD_TO_EXTERNAL_AI.zip"
DEFAULT_REPO_URL = "https://github.com/Tienkhoaa2908/vn-quant-system"

DENIED_NAME_FRAGMENTS = (
    ".env",
    "credential",
    "secret",
    "password",
    "token",
    "api_key",
    "apikey",
    "account_export",
    "portfolio_snapshot",
)

TEXT_SUFFIXES = {
    ".txt", ".md", ".json", ".csv", ".yaml", ".yml", ".toml", ".ini"
}

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|password|access[_-]?token|refresh[_-]?token)\s*[:=]\s*['\"]?([^\s,'\"}]{8,})"),
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
)

REVIEW_EVIDENCE_ALLOWLIST = (
    "historical_research_input_v22.json",
    "manifest.json",
    "model_lab_summary.json",
    "extended_history_reference_v24.json",
    "component_breadth_ablation_v27.json",
    "breadth_availability_v27.csv",
    "signal_gates_v27.csv",
    "portfolio_comparison_v27.csv",
    "decision_gates_v27.csv",
    "factor_summary_v27.csv",
    "factor_quantiles_v27.csv",
    "quantile_shape_v27.csv",
    "component_correlation_v27.csv",
    "regime_summary_v27.csv",
    "adaptive_component_weights_v27.csv",
    "frozen_component_candidate_v28.json",
    "verification_v28.csv",
    "forward_watchlist_v28.csv",
)


@dataclass(frozen=True)
class RepoMetadata:
    commit: str
    branch: str
    remote_url: str
    dirty: bool
    base_ref: str


def _run(args: Sequence[str], *, cwd: Path, check: bool = True) -> str:
    completed = subprocess.run(
        list(args),
        cwd=str(cwd),
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"AI_REVIEW_JSON_OBJECT_REQUIRED:{path.name}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _repo_metadata(repo_root: Path, base_ref: str) -> RepoMetadata:
    if not (repo_root / ".git").exists():
        raise ValueError("AI_REVIEW_REPO_GIT_REQUIRED")
    commit = _run(("git", "rev-parse", "HEAD"), cwd=repo_root)
    branch = _run(("git", "branch", "--show-current"), cwd=repo_root) or "DETACHED"
    remote_url = _run(("git", "remote", "get-url", "origin"), cwd=repo_root)
    dirty = bool(_run(("git", "status", "--porcelain"), cwd=repo_root))
    return RepoMetadata(
        commit=commit,
        branch=branch,
        remote_url=remote_url,
        dirty=dirty,
        base_ref=base_ref,
    )


def _is_denied_name(path: Path) -> bool:
    lowered = path.name.lower()
    return any(fragment in lowered for fragment in DENIED_NAME_FRAGMENTS)


def _scan_text_for_secret(path: Path) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            token = match.group(0)
            lowered = token.lower()
            if any(marker in lowered for marker in ("redacted", "masked", "example", "dummy", "changeme")):
                continue
            raise ValueError(f"AI_REVIEW_SECRET_PATTERN:{path.name}")


def _copy_evidence(source: Path, destination: Path, logical_name: str) -> dict[str, object]:
    if not source.is_file():
        raise FileNotFoundError(f"AI_REVIEW_EVIDENCE_NOT_FOUND:{source}")
    if source.name not in REVIEW_EVIDENCE_ALLOWLIST:
        raise ValueError(f"AI_REVIEW_EVIDENCE_NOT_ALLOWLISTED:{source.name}")
    if _is_denied_name(source):
        raise ValueError(f"AI_REVIEW_DENIED_FILENAME:{source.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    _scan_text_for_secret(destination)
    return {
        "logical_name": logical_name,
        "source_path": str(source),
        "bundle_path": destination.as_posix(),
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
    }


def _source_snapshot(repo_root: Path, destination: Path, metadata: RepoMetadata) -> dict[str, object]:
    _run(("git", "archive", "--format=zip", f"--output={destination}", metadata.commit), cwd=repo_root)
    return {
        "logical_name": "source_snapshot",
        "source_path": f"git:{metadata.commit}",
        "bundle_path": destination.as_posix(),
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
    }


def _write_repo_context(repo_root: Path, destination: Path, metadata: RepoMetadata) -> list[dict[str, object]]:
    destination.mkdir(parents=True, exist_ok=True)
    log_path = destination / "git_log.txt"
    log_path.write_text(
        _run(("git", "log", "--oneline", "--decorate", "-n", "100"), cwd=repo_root) + "\n",
        encoding="utf-8",
    )
    diff_stat_path = destination / "diff_stat_vs_base.txt"
    try:
        diff_stat = _run(("git", "diff", "--stat", f"{metadata.base_ref}...{metadata.commit}"), cwd=repo_root)
    except subprocess.CalledProcessError:
        diff_stat = "BASE_REF_UNAVAILABLE\n"
    diff_stat_path.write_text(diff_stat.rstrip() + "\n", encoding="utf-8")
    metadata_path = destination / "repo_metadata.json"
    _write_json(metadata_path, {
        "commit": metadata.commit,
        "branch": metadata.branch,
        "remote_url": metadata.remote_url,
        "dirty": metadata.dirty,
        "base_ref": metadata.base_ref,
    })
    rows = []
    for logical_name, path in (
        ("repo_metadata", metadata_path),
        ("git_log", log_path),
        ("diff_stat_vs_base", diff_stat_path),
    ):
        rows.append({
            "logical_name": logical_name,
            "source_path": "generated",
            "bundle_path": path.as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return rows


def _sqlite_inventory(store: Path, destination: Path, sample_rows: int) -> list[dict[str, object]]:
    if not store.is_file():
        raise FileNotFoundError(f"AI_REVIEW_STORE_NOT_FOUND:{store}")
    destination.mkdir(parents=True, exist_ok=True)
    inventory: dict[str, object] = {
        "store_path": str(store),
        "store_sha256": _sha256(store),
        "store_size_bytes": store.stat().st_size,
        "full_store_included": False,
        "tables": [],
    }
    artifacts: list[dict[str, object]] = []
    with sqlite3.connect(f"file:{store.as_posix()}?mode=ro", uri=True) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        for table in tables:
            lowered = table.lower()
            if any(fragment in lowered for fragment in ("secret", "token", "credential", "account", "session")):
                inventory["tables"].append({
                    "table": table,
                    "excluded_from_sample": True,
                    "reason": "SENSITIVE_NAME_GUARD",
                })
                continue
            quoted = '"' + table.replace('"', '""') + '"'
            columns = [dict(zip(("cid", "name", "type", "notnull", "default", "pk"), row))
                       for row in connection.execute(f"PRAGMA table_info({quoted})")]
            row_count = int(connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
            inventory["tables"].append({
                "table": table,
                "row_count": row_count,
                "columns": columns,
                "excluded_from_sample": False,
            })
            limit = max(0, min(sample_rows, row_count))
            if limit == 0:
                continue
            sample = connection.execute(f"SELECT * FROM {quoted} LIMIT ?", (limit,)).fetchall()
            sample_path = destination / f"sample_{re.sub(r'[^A-Za-z0-9_.-]+', '_', table)}.csv"
            with sample_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow([column["name"] for column in columns])
                writer.writerows(sample)
            artifacts.append({
                "logical_name": f"sqlite_sample:{table}",
                "source_path": str(store),
                "bundle_path": sample_path.as_posix(),
                "size_bytes": sample_path.stat().st_size,
                "sha256": _sha256(sample_path),
            })
    inventory_path = destination / "sqlite_inventory.json"
    _write_json(inventory_path, inventory)
    artifacts.append({
        "logical_name": "sqlite_inventory",
        "source_path": str(store),
        "bundle_path": inventory_path.as_posix(),
        "size_bytes": inventory_path.stat().st_size,
        "sha256": _sha256(inventory_path),
    })
    return artifacts


def _extract_v27_summary(v27_output: Path) -> dict[str, object]:
    report_path = v27_output / "component_breadth_ablation_v27.json"
    report = _json(report_path)
    decision_path = v27_output / "decision_gates_v27.csv"
    passing: list[dict[str, str]] = []
    if decision_path.is_file():
        with decision_path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if str(row.get("v27_decision_gate_passed", "")).lower() in {"true", "1"}:
                    passing.append(dict(row))
    return {
        "status": report.get("status"),
        "experiment": report.get("experiment"),
        "walk_forward_fold_count": report.get("walk_forward_fold_count"),
        "walk_forward_first_test_date": report.get("walk_forward_first_test_date"),
        "walk_forward_last_test_date": report.get("walk_forward_last_test_date"),
        "recommendation": report.get("recommendation"),
        "sensitivity_analysis_only": report.get("sensitivity_analysis_only"),
        "independent_holdout": report.get("independent_holdout"),
        "research_eligible": report.get("research_eligible"),
        "live_capital_approved": report.get("live_capital_approved"),
        "passing_decision_rows": passing,
    }


def _project_context(repo_url: str, metadata: RepoMetadata, v27_summary: Mapping[str, object], v28_present: bool) -> str:
    return f"""# VN Quant System — External Review Context

## Repository snapshot

- Public repository: {repo_url}
- Exact commit: `{metadata.commit}`
- Branch: `{metadata.branch}`
- Base comparison: `{metadata.base_ref}`
- Working tree dirty when bundled: `{str(metadata.dirty).lower()}`

## System objective

Build a Vietnam-equity quantitative research and paper-trading system:

`data → quality checks → point-in-time universe → features → stock ranking → portfolio allocation → backtest → paper trading`

Current MVP constraints:

- Daily OHLCV; long-only; no margin; no shorting.
- MA250 market regime and eligibility filter.
- Monthly ranking with a 20-session predictive label.
- Walk-forward evaluation with label-end purge.
- Portfolio limits: 15% per symbol and 25% per sector when sector data is trusted.
- Costs include brokerage, sell tax, slippage, odd-lot execution, and cash handling.
- T+1 is execution accounting only, never predictive-quality evidence.
- No automatic live orders and no live-capital approval.

## Current evidence state

- V27 status: `{v27_summary.get('status')}`
- V27 recommendation: `{v27_summary.get('recommendation')}`
- Walk-forward folds: `{v27_summary.get('walk_forward_fold_count')}`
- Test range: `{v27_summary.get('walk_forward_first_test_date')}` to `{v27_summary.get('walk_forward_last_test_date')}`
- Passing V27 post-selection rows: `{len(v27_summary.get('passing_decision_rows', []))}`
- V28 artifact present in this bundle: `{str(v28_present).lower()}`

## Mandatory interpretation

V27 is a post-review sensitivity analysis. A configuration that passed V27 is not an independent holdout result. The historical store still carries the warnings `PRICE_BASIS_CHUA_XAC_NHAN`, incomplete corporate-action handling, non-point-in-time candidate union, and unresolved survivorship bias. Treat any candidate as research/paper only until those blockers and a genuinely future holdout are resolved.
"""


def _review_prompt(repo_url: str, metadata: RepoMetadata) -> str:
    return f"""# Prompt for the independent AI reviewer

You are an independent quantitative-research auditor. Review the attached VN Quant System bundle and the public repository at `{repo_url}` pinned to commit `{metadata.commit}`.

Do not merely summarize. Search for errors, hidden assumptions, leakage, selection bias, unrealistic execution assumptions, and architectural weaknesses. Cite exact bundle paths, JSON fields, CSV columns, functions, or test names for every material claim.

## Required review areas

1. Reconstruct the end-to-end architecture and identify the canonical path versus experimental paths.
2. Audit data lineage, duplicate handling, timestamp semantics, price basis, corporate actions, survivorship bias, and point-in-time universe construction.
3. Audit target construction, 20-session label horizon, walk-forward chronology, train/validation/test boundaries, label-end purge, and nested policy selection.
4. Check whether any metric, feature weight, breadth, regime rule, or replacement policy was selected after looking at the same test period.
5. Evaluate statistical strength: IC stability, quantile monotonicity, multiple-testing risk, leave-best-period-out behavior, regime dependence, and effective sample size.
6. Evaluate portfolio construction: Top-K concentration, inverse-volatility logic, cash slots, symbol/sector caps, turnover, fees, sell tax, slippage, odd lots, and contribution-aware allocation.
7. Review software engineering: reproducibility, immutable artifacts, hashes, failure modes, tests, public/private boundaries, and dependency risk.
8. Separate verified facts, reasonable inferences, and unknowns. Do not fill unsupported gaps.
9. Produce a prioritized remediation plan with three levels: blockers before more model tuning, high-value next experiments, and later infrastructure improvements.
10. Give an explicit verdict using these labels only:
   - `INVALID_EVIDENCE`
   - `TECHNICAL_VALIDATION_ONLY`
   - `PROMISING_POST_SELECTION_CANDIDATE`
   - `READY_FOR_FUTURE_PAPER_HOLDOUT`
   - `HISTORICAL_REFERENCE_SUPPORTED`
   - `LIVE_CAPITAL_SUPPORTED`

`LIVE_CAPITAL_SUPPORTED` must not be used unless the evidence itself supports it. Current project metadata explicitly says live capital is not approved.

## Required output structure

- Executive verdict
- Evidence map
- Critical blockers
- Leakage and selection-bias audit
- Data-quality and market-microstructure audit
- Model and statistical audit
- Portfolio and execution audit
- Software/reproducibility audit
- What the current team may be overlooking
- Prioritized next actions
- Questions that cannot be answered from the bundle

Do not use T+1 outcomes to judge model predictive quality. Do not treat V27 or V28 as an independent future holdout merely because the code rebuilds them reproducibly.
"""


def _open_questions() -> str:
    return """# Open questions for the reviewer

1. Is the historical universe genuinely point-in-time, including delisted and renamed securities?
2. Is the DNSE price series adjusted, unadjusted, or mixed around corporate actions?
3. Does the label use an execution price realistically available after the signal?
4. Are monthly samples independent enough for the chosen significance thresholds?
5. How should multiple testing across models, feature blends, breadths, and policy variants be controlled?
6. Does the fixed 3% mean Rank IC gate make sense for this universe and sample size?
7. Does leave-best-month-out sufficiently control concentration, or is block bootstrap required?
8. Is the adaptive IC weighting stable, or does it amplify noisy regime shifts?
9. Should the objective rank relative returns, residualized returns, or downside-avoidance probability?
10. Is Top-10 appropriate when the eligible universe can be as small as 13 names?
11. Is equal-weight evaluation masking the effect of the intended inverse-volatility allocator?
12. Are sector caps enforceable with point-in-time sector metadata?
13. Are odd-lot fees, liquidity, price limits, and partial fills modeled conservatively enough?
14. Does MA250 regime filtering create hidden timing or selection interactions?
15. Is RISK_OFF weakness structural, or an artifact of small sample size?
16. Should future validation freeze the score, breadth, regime overlay, and all thresholds simultaneously?
17. What minimum future holdout duration and number of observations are defensible?
18. Which tests are missing for artifact tampering, chronology drift, and source-data revisions?
19. Which external libraries would reduce risk without replacing Vietnam-specific execution logic?
20. What evidence would be required before contribution planning or live-capital use is justified?
"""


def _reproduction(metadata: RepoMetadata) -> str:
    return f"""# Reproduction instructions

## Source

```bash
git clone {metadata.remote_url}
cd vn-quant-system
git checkout {metadata.commit}
uv sync --frozen --python 3.12
PYTHONPATH=src uv run --python 3.12 python -m unittest discover -s tests -p 'test_*.py' -v
```

## Evidence

- `source/source_snapshot.zip` is a complete tracked-file snapshot at the exact commit.
- `evidence/` contains allowlisted reports and CSV diagnostics.
- `research_input/daily_prediction_input.zip` is included only when the bundle was built with `--include-research-input`.
- `data_inventory/` contains SQLite schema, row counts, hashes, and deterministic samples; the full database is deliberately excluded.
- `artifact_manifest.json` contains SHA-256 hashes for every packaged file.

The receiving reviewer should first verify hashes, then inspect the project context and review prompt.
"""


def _manifest_files(root: Path, *, exclude: Iterable[Path] = ()) -> list[dict[str, object]]:
    excluded = {path.resolve() for path in exclude}
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() in excluded:
            continue
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return rows


def _stable_zip(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def build_review_bundle(
    *,
    repo_root: Path,
    historical_input_dir: Path,
    model_output: Path,
    v27_output_dir: Path,
    output_dir: Path,
    repo_url: str = DEFAULT_REPO_URL,
    v24_report: Path | None = None,
    v28_output_dir: Path | None = None,
    store: Path | None = None,
    include_research_input: bool = True,
    include_source_snapshot: bool = True,
    allow_dirty: bool = False,
    base_ref: str = "origin/main",
    sqlite_sample_rows: int = 50,
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    historical_input_dir = historical_input_dir.resolve()
    model_output = model_output.resolve()
    v27_output_dir = v27_output_dir.resolve()
    output_dir = output_dir.resolve()
    metadata = _repo_metadata(repo_root, base_ref)
    if metadata.dirty and not allow_dirty:
        raise ValueError("AI_REVIEW_DIRTY_WORKTREE")
    if output_dir.exists():
        raise FileExistsError(f"AI_REVIEW_OUTPUT_EXISTS:{output_dir}")
    required_dirs = (historical_input_dir, model_output, v27_output_dir)
    if any(not path.is_dir() for path in required_dirs):
        raise ValueError("AI_REVIEW_REQUIRED_DIRECTORY_MISSING")

    staging = output_dir.with_name(f".{output_dir.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    artifacts: list[dict[str, object]] = []
    try:
        source_dir = staging / "source"
        artifacts.extend(_write_repo_context(repo_root, source_dir, metadata))
        if include_source_snapshot:
            snapshot = source_dir / "source_snapshot.zip"
            artifacts.append(_source_snapshot(repo_root, snapshot, metadata))

        evidence_dir = staging / "evidence"
        evidence_specs: list[tuple[str, Path]] = [
            ("historical_input_report", historical_input_dir / "historical_research_input_v22.json"),
            ("historical_input_manifest", historical_input_dir / "manifest.json"),
            ("model_lab_summary", model_output / "model_lab_summary.json"),
            ("v27_report", v27_output_dir / "component_breadth_ablation_v27.json"),
            ("v27_breadth_availability", v27_output_dir / "breadth_availability_v27.csv"),
            ("v27_signal_gates", v27_output_dir / "signal_gates_v27.csv"),
            ("v27_portfolio_comparison", v27_output_dir / "portfolio_comparison_v27.csv"),
            ("v27_decision_gates", v27_output_dir / "decision_gates_v27.csv"),
            ("v27_factor_summary", v27_output_dir / "factor_summary_v27.csv"),
            ("v27_factor_quantiles", v27_output_dir / "factor_quantiles_v27.csv"),
            ("v27_quantile_shape", v27_output_dir / "quantile_shape_v27.csv"),
            ("v27_component_correlation", v27_output_dir / "component_correlation_v27.csv"),
            ("v27_regime_summary", v27_output_dir / "regime_summary_v27.csv"),
            ("v27_adaptive_weights", v27_output_dir / "adaptive_component_weights_v27.csv"),
        ]
        if v24_report is not None:
            evidence_specs.append(("v24_report", v24_report.resolve()))
        v28_present = bool(v28_output_dir and v28_output_dir.resolve().is_dir())
        if v28_present and v28_output_dir is not None:
            v28 = v28_output_dir.resolve()
            evidence_specs.extend([
                ("v28_report", v28 / "frozen_component_candidate_v28.json"),
                ("v28_verification", v28 / "verification_v28.csv"),
                ("v28_forward_watchlist", v28 / "forward_watchlist_v28.csv"),
            ])
        for logical_name, source in evidence_specs:
            artifacts.append(_copy_evidence(source, evidence_dir / source.name, logical_name))

        input_zip = historical_input_dir / "daily_prediction_input.zip"
        if include_research_input:
            if not input_zip.is_file():
                raise FileNotFoundError("AI_REVIEW_RESEARCH_INPUT_NOT_FOUND")
            research_dir = staging / "research_input"
            research_dir.mkdir()
            destination = research_dir / input_zip.name
            shutil.copy2(input_zip, destination)
            artifacts.append({
                "logical_name": "research_input_zip",
                "source_path": str(input_zip),
                "bundle_path": destination.as_posix(),
                "size_bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
            })

        if store is not None:
            artifacts.extend(_sqlite_inventory(store.resolve(), staging / "data_inventory", sqlite_sample_rows))

        v27_summary = _extract_v27_summary(v27_output_dir)
        docs = {
            "README_FIRST.md": _project_context(repo_url, metadata, v27_summary, v28_present),
            "PROMPT_FOR_EXTERNAL_AI.md": _review_prompt(repo_url, metadata),
            "OPEN_QUESTIONS.md": _open_questions(),
            "REPRODUCTION.md": _reproduction(metadata),
        }
        for name, content in docs.items():
            path = staging / name
            path.write_text(content.rstrip() + "\n", encoding="utf-8")
            artifacts.append({
                "logical_name": name,
                "source_path": "generated",
                "bundle_path": path.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })

        evidence_index = staging / "artifact_index.csv"
        _write_csv(evidence_index, artifacts)

        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "repo_url": repo_url,
            "repo_commit": metadata.commit,
            "repo_branch": metadata.branch,
            "repo_dirty": metadata.dirty,
            "source_snapshot_included": include_source_snapshot,
            "research_input_included": include_research_input,
            "full_sqlite_store_included": False,
            "sqlite_inventory_included": store is not None,
            "v28_evidence_included": v28_present,
            "v27_summary": v27_summary,
            "security_contract": {
                "credentials_included": False,
                "broker_account_export_included": False,
                "automatic_live_orders_allowed": False,
                "live_capital_approved": False,
            },
            "reviewer_entrypoint": "README_FIRST.md",
            "reviewer_prompt": "PROMPT_FOR_EXTERNAL_AI.md",
        }
        _write_json(staging / REPORT_FILE, report)

        manifest_rows = _manifest_files(staging)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "repo_commit": metadata.commit,
            "file_count": len(manifest_rows),
            "files": manifest_rows,
        }
        _write_json(staging / "artifact_manifest.json", manifest)

        os.replace(staging, output_dir)
        bundle_zip = output_dir.parent / f"{output_dir.name}.zip"
        if bundle_zip.exists():
            raise FileExistsError(f"AI_REVIEW_BUNDLE_ZIP_EXISTS:{bundle_zip}")
        _stable_zip(output_dir, bundle_zip)
        return {
            **report,
            "output_dir": str(output_dir),
            "bundle_zip": str(bundle_zip),
            "bundle_zip_sha256": _sha256(bundle_zip),
        }
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.ai_review_bundle_v1")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--historical-input-dir", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--v27-output-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--v24-report", type=Path)
    parser.add_argument("--v28-output-dir", type=Path)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--sqlite-sample-rows", type=int, default=50)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--include-research-input", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-source-snapshot", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_review_bundle(
            repo_root=args.repo_root,
            historical_input_dir=args.historical_input_dir,
            model_output=args.model_output,
            v27_output_dir=args.v27_output_dir,
            output_dir=args.output_dir,
            repo_url=args.repo_url,
            v24_report=args.v24_report,
            v28_output_dir=args.v28_output_dir,
            store=args.store,
            include_research_input=args.include_research_input,
            include_source_snapshot=args.include_source_snapshot,
            allow_dirty=args.allow_dirty,
            base_ref=args.base_ref,
            sqlite_sample_rows=args.sqlite_sample_rows,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = ["SCHEMA_VERSION", "REPORT_FILE", "build_review_bundle", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
