"""V26 external quantitative-finance ecosystem catalog and clone manager.

This module keeps third-party research repositories outside the main source tree.
It never installs or executes cloned code.  A clone is shallow, its exact HEAD
and detected licence file hash are written to a lock file, and later verification
is fully offline.

The catalog separates permissive optional integrations from architecture-only or
licence-restricted research.  No external repository can approve research quality,
live capital or automatic orders.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Iterable, Mapping, Sequence

SCHEMA_VERSION = "external_quant_ecosystem_v26"
DEFAULT_LOCK_FILE = "external_quant_repositories_v26.lock.json"
PERMISSIVE_LICENSES = {"MIT", "Apache-2.0", "BSD-3-Clause"}
RESTRICTED_LICENSES = {"GPL-3.0", "ALL-RIGHTS-RESERVED", "UNKNOWN-REVIEW-REQUIRED"}
GITHUB_HTTPS = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")


@dataclass(frozen=True)
class RepositorySpec:
    slug: str
    url: str
    category: str
    tier: str
    expected_license: str
    integration_mode: str
    priority: int
    rationale: str


CATALOG: tuple[RepositorySpec, ...] = (
    RepositorySpec(
        "microsoft-qlib",
        "https://github.com/microsoft/qlib.git",
        "research-platform",
        "core",
        "MIT",
        "ADOPT_PATTERNS",
        1,
        "Workflow, dataset, model-zoo and online-rolling patterns; do not replace VN-specific execution.",
    ),
    RepositorySpec(
        "alphalens-reloaded",
        "https://github.com/stefan-jansen/alphalens-reloaded.git",
        "factor-diagnostics",
        "core",
        "Apache-2.0",
        "OPTIONAL_ADAPTER",
        1,
        "Factor IC, quantile return, turnover and grouped-analysis cross-checks.",
    ),
    RepositorySpec(
        "pyportfolioopt",
        "https://github.com/PyPortfolio/PyPortfolioOpt.git",
        "portfolio-optimization",
        "core",
        "MIT",
        "OPTIONAL_ADAPTER",
        1,
        "Minimum-volatility and covariance-shrinkage benchmark under long-only caps.",
    ),
    RepositorySpec(
        "skfolio",
        "https://github.com/skfolio/skfolio.git",
        "portfolio-optimization",
        "core",
        "BSD-3-Clause",
        "RESEARCH_BENCHMARK",
        2,
        "Scikit-learn-compatible portfolio cross-validation and stress testing.",
    ),
    RepositorySpec(
        "optuna",
        "https://github.com/optuna/optuna.git",
        "hyperparameter-optimization",
        "core",
        "MIT",
        "FUTURE_NESTED_ADAPTER",
        2,
        "Constrained search only inside nested validation; never tune on outer test.",
    ),
    RepositorySpec(
        "pandera",
        "https://github.com/unionai-oss/pandera.git",
        "data-quality",
        "core",
        "MIT",
        "OPTIONAL_SCHEMA_AUDIT",
        1,
        "Independent dataframe-schema audit alongside existing fail-closed validators.",
    ),
    RepositorySpec(
        "exchange-calendars",
        "https://github.com/gerrymanoim/exchange_calendars.git",
        "market-calendar",
        "core",
        "Apache-2.0",
        "ADOPT_PATTERNS",
        2,
        "Reference architecture for a future HOSE/HNX/UPCOM calendar implementation and tests.",
    ),
    RepositorySpec(
        "dvc",
        "https://github.com/iterative/dvc.git",
        "data-lineage",
        "core",
        "Apache-2.0",
        "OPTIONAL_TOOLING",
        2,
        "Dataset and model lineage for large local artifacts without committing raw data.",
    ),
    RepositorySpec(
        "feast",
        "https://github.com/feast-dev/feast.git",
        "feature-store",
        "core",
        "Apache-2.0",
        "ADOPT_PATTERNS",
        3,
        "Point-in-time feature retrieval patterns; deployment is premature for the current local MVP.",
    ),
    RepositorySpec(
        "vnstock",
        "https://github.com/thinh-vu/vnstock.git",
        "vietnam-data",
        "core",
        "UNKNOWN-REVIEW-REQUIRED",
        "SOURCE_CROSSCHECK_ONLY",
        1,
        "Vietnam-market source cross-check and metadata discovery; DNSE remains canonical for the current store.",
    ),
    RepositorySpec(
        "vectorbt",
        "https://github.com/polakowo/vectorbt.git",
        "backtest-research",
        "extended",
        "UNKNOWN-REVIEW-REQUIRED",
        "INDEPENDENT_CROSSCHECK",
        2,
        "Fast parameter-sweep and arithmetic cross-check; not the canonical VN execution engine.",
    ),
    RepositorySpec(
        "zipline-reloaded",
        "https://github.com/stefan-jansen/zipline-reloaded.git",
        "event-driven-backtest",
        "extended",
        "Apache-2.0",
        "ARCHITECTURE_RESEARCH",
        3,
        "Event-driven simulation and asset-lifecycle patterns; direct ingestion is US-centric.",
    ),
    RepositorySpec(
        "pyfolio-reloaded",
        "https://github.com/stefan-jansen/pyfolio-reloaded.git",
        "performance-analytics",
        "extended",
        "Apache-2.0",
        "OPTIONAL_REPORT_CROSSCHECK",
        2,
        "Risk and performance tear-sheet cross-check from monthly/daily return streams.",
    ),
    RepositorySpec(
        "quantstats",
        "https://github.com/ranaroussi/quantstats.git",
        "performance-analytics",
        "extended",
        "UNKNOWN-REVIEW-REQUIRED",
        "OPTIONAL_REPORT_CROSSCHECK",
        3,
        "Additional drawdown, rolling and Monte-Carlo diagnostics; not a decision gate by itself.",
    ),
    RepositorySpec(
        "riskfolio-lib",
        "https://github.com/dcajasn/Riskfolio-Lib.git",
        "portfolio-risk",
        "extended",
        "BSD-3-Clause",
        "RESEARCH_BENCHMARK",
        3,
        "CVaR and alternative risk-measure allocation sensitivity analysis.",
    ),
    RepositorySpec(
        "ta",
        "https://github.com/bukosabino/ta.git",
        "feature-engineering",
        "extended",
        "MIT",
        "FEATURE_CANDIDATE_LIBRARY",
        3,
        "Technical-indicator candidates must pass leakage, redundancy and stability tests before adoption.",
    ),
    RepositorySpec(
        "tsfresh",
        "https://github.com/blue-yonder/tsfresh.git",
        "feature-engineering",
        "extended",
        "MIT",
        "OFFLINE_FEATURE_DISCOVERY",
        4,
        "Automated feature discovery only inside nested research; never run blindly in production.",
    ),
    RepositorySpec(
        "mlflow",
        "https://github.com/mlflow/mlflow.git",
        "experiment-tracking",
        "extended",
        "Apache-2.0",
        "OPTIONAL_TOOLING",
        3,
        "Experiment lineage and model registry after the local artifact contract stabilizes.",
    ),
    RepositorySpec(
        "backtrader",
        "https://github.com/mementum/backtrader.git",
        "event-driven-backtest",
        "research-only",
        "GPL-3.0",
        "ARCHITECTURE_ONLY_NO_CODE_COPY",
        5,
        "Copyleft licence and stale architecture make direct integration unsuitable.",
    ),
    RepositorySpec(
        "mlfinlab",
        "https://github.com/hudson-and-thames/mlfinlab.git",
        "financial-ml-methods",
        "research-only",
        "ALL-RIGHTS-RESERVED",
        "CONCEPTS_ONLY_NO_CODE_COPY",
        5,
        "Study public descriptions of purging, overfitting and bet sizing; do not copy restricted code.",
    ),
    RepositorySpec(
        "vnpy",
        "https://github.com/vnpy/vnpy.git",
        "trading-platform",
        "research-only",
        "UNKNOWN-REVIEW-REQUIRED",
        "ARCHITECTURE_ONLY",
        5,
        "Gateway/event-engine patterns only; it targets a different market and execution stack.",
    ),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_clone_root(root: Path) -> Path:
    target = Path(root).expanduser().resolve()
    repository = _repo_root()
    if target == repository or _is_within(target, repository):
        raise ValueError("V26_EXTERNAL_ROOT_MUST_BE_OUTSIDE_MAIN_REPOSITORY")
    if repository == target or _is_within(repository, target):
        raise ValueError("V26_EXTERNAL_ROOT_MUST_NOT_CONTAIN_MAIN_REPOSITORY")
    return target


def _catalog_by_slug() -> dict[str, RepositorySpec]:
    result: dict[str, RepositorySpec] = {}
    for spec in CATALOG:
        if spec.slug in result:
            raise ValueError(f"V26_DUPLICATE_REPOSITORY_SLUG:{spec.slug}")
        if not GITHUB_HTTPS.fullmatch(spec.url):
            raise ValueError(f"V26_INVALID_GITHUB_URL:{spec.slug}")
        result[spec.slug] = spec
    return result


def select_repositories(
    selection: str,
    *,
    include_restricted: bool = False,
) -> tuple[RepositorySpec, ...]:
    catalog = _catalog_by_slug()
    token = str(selection or "core").strip().lower()
    if token in {"core", "extended", "all"}:
        tiers = {
            "core": {"core"},
            "extended": {"core", "extended"},
            "all": {"core", "extended", "research-only"},
        }[token]
        selected = [spec for spec in CATALOG if spec.tier in tiers]
    else:
        requested = [item.strip() for item in token.split(",") if item.strip()]
        unknown = [item for item in requested if item not in catalog]
        if unknown:
            raise ValueError("V26_UNKNOWN_REPOSITORY:" + "|".join(sorted(unknown)))
        selected = [catalog[item] for item in requested]
    if not include_restricted:
        selected = [
            spec
            for spec in selected
            if spec.expected_license not in RESTRICTED_LICENSES
        ]
    return tuple(sorted(selected, key=lambda item: (item.priority, item.slug)))


def catalog_payload() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "READY",
        "repository_count": len(CATALOG),
        "permissive_repository_count": sum(
            spec.expected_license in PERMISSIVE_LICENSES for spec in CATALOG
        ),
        "restricted_or_review_required_count": sum(
            spec.expected_license in RESTRICTED_LICENSES for spec in CATALOG
        ),
        "repositories": [asdict(spec) for spec in CATALOG],
        "third_party_code_vendored": False,
        "third_party_code_executed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }


def _run_git(arguments: Sequence[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "git failed").strip()
        detail = detail.replace("\r", " ").replace("\n", " ")[:600]
        raise RuntimeError(f"V26_GIT_FAILED:{arguments[0]}:{detail}")
    return completed.stdout.strip()


def _license_metadata(repository: Path) -> dict[str, object]:
    candidates = (
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "LICENCE",
        "COPYING",
        "COPYING.md",
    )
    for name in candidates:
        path = repository / name
        if path.is_file():
            payload = path.read_bytes()
            return {
                "license_file": name,
                "license_file_sha256": sha256(payload).hexdigest(),
                "license_file_size": len(payload),
            }
    return {
        "license_file": "",
        "license_file_sha256": "",
        "license_file_size": 0,
    }


def inspect_clone(path: Path, spec: RepositorySpec) -> dict[str, object]:
    repository = Path(path).resolve()
    if not (repository / ".git").exists():
        raise ValueError(f"V26_NOT_A_GIT_CLONE:{spec.slug}")
    head = _run_git(("rev-parse", "HEAD"), cwd=repository)
    remote = _run_git(("remote", "get-url", "origin"), cwd=repository)
    branch = _run_git(("branch", "--show-current"), cwd=repository)
    dirty = bool(_run_git(("status", "--porcelain"), cwd=repository))
    return {
        "slug": spec.slug,
        "path": str(repository),
        "url": spec.url,
        "remote_url": remote,
        "head": head,
        "branch": branch,
        "dirty": dirty,
        "expected_license": spec.expected_license,
        "integration_mode": spec.integration_mode,
        **_license_metadata(repository),
    }


def clone_repositories(
    root: Path,
    *,
    selection: str = "core",
    include_restricted: bool = False,
    reuse_existing: bool = False,
    lock_file: Path | None = None,
) -> dict[str, object]:
    destination = validate_clone_root(root)
    destination.mkdir(parents=True, exist_ok=True)
    specs = select_repositories(selection, include_restricted=include_restricted)
    if not specs:
        raise ValueError("V26_NO_REPOSITORIES_SELECTED")
    records: list[dict[str, object]] = []
    failures: dict[str, str] = {}
    for spec in specs:
        target = destination / spec.slug
        try:
            if target.exists():
                if not reuse_existing:
                    raise FileExistsError(f"V26_CLONE_EXISTS:{target}")
            else:
                _run_git(("clone", "--depth", "1", "--no-tags", spec.url, str(target)))
            records.append(inspect_clone(target, spec))
        except Exception as exc:  # continue to publish a complete failure report
            failures[spec.slug] = f"{type(exc).__name__}:{exc}"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS" if not failures else "PARTIAL_FAILURE",
        "root": str(destination),
        "selection": selection,
        "include_restricted": include_restricted,
        "repository_count": len(records),
        "requested_repository_count": len(specs),
        "repositories": records,
        "failures": failures,
        "third_party_code_vendored": False,
        "third_party_code_executed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    output = Path(lock_file).expanduser().resolve() if lock_file else destination / DEFAULT_LOCK_FILE
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, output)
    return {**payload, "lock_file": str(output)}


def verify_lock(root: Path, lock_file: Path) -> dict[str, object]:
    destination = validate_clone_root(root)
    lock = json.loads(Path(lock_file).read_text(encoding="utf-8-sig"))
    if not isinstance(lock, dict):
        raise ValueError("V26_LOCK_OBJECT_REQUIRED")
    rows = lock.get("repositories")
    if not isinstance(rows, list):
        raise ValueError("V26_LOCK_REPOSITORIES_REQUIRED")
    catalog = _catalog_by_slug()
    checks: list[dict[str, object]] = []
    mismatches: list[str] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("V26_LOCK_ROW_OBJECT_REQUIRED")
        slug = str(raw.get("slug") or "")
        if slug not in catalog:
            raise ValueError(f"V26_LOCK_UNKNOWN_SLUG:{slug}")
        actual = inspect_clone(destination / slug, catalog[slug])
        expected_head = str(raw.get("head") or "")
        expected_license_hash = str(raw.get("license_file_sha256") or "")
        head_matches = actual["head"] == expected_head
        license_matches = actual["license_file_sha256"] == expected_license_hash
        clean = not bool(actual["dirty"])
        if not (head_matches and license_matches and clean):
            mismatches.append(slug)
        checks.append({
            "slug": slug,
            "head_matches": head_matches,
            "license_hash_matches": license_matches,
            "working_tree_clean": clean,
            "actual_head": actual["head"],
            "expected_head": expected_head,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "VERIFIED" if not mismatches else "MISMATCH",
        "root": str(destination),
        "lock_file": str(Path(lock_file).resolve()),
        "checks": checks,
        "mismatches": mismatches,
        "third_party_code_executed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }


def _write_json(path: Path, payload: object) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.external_quant_ecosystem_v26"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("catalog")
    catalog.add_argument("--output-json", type=Path)
    clone = sub.add_parser("clone")
    clone.add_argument("--root", type=Path, required=True)
    clone.add_argument("--selection", default="core")
    clone.add_argument("--include-restricted", action="store_true")
    clone.add_argument("--reuse-existing", action="store_true")
    clone.add_argument("--lock-file", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--lock-file", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "catalog":
            result = catalog_payload()
            if args.output_json:
                _write_json(args.output_json, result)
        elif args.command == "clone":
            result = clone_repositories(
                args.root,
                selection=args.selection,
                include_restricted=args.include_restricted,
                reuse_existing=args.reuse_existing,
                lock_file=args.lock_file,
            )
        else:
            result = verify_lock(args.root, args.lock_file)
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") not in {"PARTIAL_FAILURE", "MISMATCH"} else 2


__all__ = [
    "SCHEMA_VERSION",
    "RepositorySpec",
    "CATALOG",
    "catalog_payload",
    "select_repositories",
    "validate_clone_root",
    "clone_repositories",
    "verify_lock",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
