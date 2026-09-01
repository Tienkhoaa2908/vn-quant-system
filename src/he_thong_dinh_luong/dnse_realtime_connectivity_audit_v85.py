"""V85 read-only forensic audit for DNSE realtime connectivity.

This module intentionally does NOT install/upgrade packages, mutate workstation
state, open an order surface, or place orders.  It inventories the canonical
runtime, fingerprints the installed DNSE streaming implementation, scans the
approved local web for realtime integration, samples the local read-only
``/api/realtime`` endpoint, and optionally exercises the existing REST smoke.

The purpose is to distinguish four independent layers:

1. localhost HTTP endpoint health;
2. existing DNSE REST/account connectivity;
3. installed DNSE WebSocket SDK implementation/risk signatures;
4. local-only realtime integration code that may not exist in Git history.

Secrets are never emitted.  Source matches are represented only by path, hash,
line number and matched marker names.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
from importlib import metadata, util
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Iterable, Mapping
from urllib import error as urlerror
from urllib import request as urlrequest


AUDIT_VERSION = "V85_DNSE_REALTIME_CONNECTIVITY_AUDIT"
SECRET_BASENAMES = {"dnse_credentials.json", ".env", ".env.local", ".env.production"}
SCAN_MARKERS = {
    "/api/realtime": "API_REALTIME",
    "DnseMarketStream": "OLD_MARKET_STREAM",
    "DnseTradingStream": "OLD_TRADING_STREAM",
    "TradingClient": "TRADING_CLIENT",
    "websocket": "WEBSOCKET",
    "Reconnect attempt": "RECONNECT_LOG",
    "realtime": "REALTIME",
}


@dataclass(frozen=True)
class SourceMatch:
    path: str
    sha256: str
    tracked: bool
    dirty: bool
    marker_lines: dict[str, list[int]]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _git_bool(repo_root: Path, args: list[str]) -> bool:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False,
    )
    return completed.returncode == 0


def _is_tracked(repo_root: Path, relative: str) -> bool:
    return _git_bool(repo_root, ["ls-files", "--error-unmatch", "--", relative])


def _is_dirty(repo_root: Path, relative: str) -> bool:
    return not _git_bool(repo_root, ["diff", "--quiet", "--", relative])


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _candidate_text_files(repo_root: Path, system_root: Path) -> Iterable[Path]:
    roots = [
        repo_root / "src" / "he_thong_dinh_luong",
        system_root / "src" / "vn_quant_local",
        system_root / "web",
    ]
    allowed = {".py", ".js", ".html", ".css", ".json", ".md", ".sh"}
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            if path.name.lower() in SECRET_BASENAMES:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield resolved


def scan_local_realtime(repo_root: Path, system_root: Path) -> list[SourceMatch]:
    matches: list[SourceMatch] = []
    for path in _candidate_text_files(repo_root, system_root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        marker_lines: dict[str, list[int]] = {}
        lines = text.splitlines()
        for needle, label in SCAN_MARKERS.items():
            hit = [i for i, line in enumerate(lines, start=1) if needle.lower() in line.lower()]
            if hit:
                marker_lines[label] = hit[:100]
        if not marker_lines:
            continue
        rel = _relative(repo_root, path)
        matches.append(SourceMatch(
            path=rel,
            sha256=_sha256(path),
            tracked=_is_tracked(repo_root, rel),
            dirty=_is_dirty(repo_root, rel),
            marker_lines=marker_lines,
        ))
    return sorted(matches, key=lambda x: x.path)


def _function_chunk(text: str, name: str, limit: int = 5000) -> str:
    match = re.search(rf"(?m)^\s*(?:async\s+)?def\s+{re.escape(name)}\s*\(", text)
    if not match:
        return ""
    start = match.start()
    next_match = re.search(r"(?m)^\s*(?:async\s+)?def\s+\w+\s*\(", text[match.end():])
    end = match.end() + next_match.start() if next_match else min(len(text), start + limit)
    return text[start:min(end, start + limit)]


def detect_legacy_stream_signatures(text_by_name: Mapping[str, str]) -> dict[str, object]:
    auth_text = "\n".join(
        value for key, value in text_by_name.items()
        if key.endswith("_stream_auth.py") or key.endswith("auth.py")
    )
    base_text = "\n".join(
        value for key, value in text_by_name.items()
        if key.endswith("_base_stream.py") or key.endswith("connection.py")
    )
    reconnect = _function_chunk(base_text, "_reconnect") or _function_chunk(base_text, "reconnect")
    connect_pos = reconnect.find("_connect(")
    if connect_pos < 0:
        connect_pos = reconnect.find(".connect(")
    before_connect = reconnect[:connect_pos] if connect_pos >= 0 else reconnect

    nonce_int = bool(re.search(r"nonce\s*=\s*int\s*\(", auth_text)) and bool(
        re.search(r"[\"']nonce[\"']\s*:\s*nonce\b", auth_text)
    )
    nonce_string = bool(re.search(r"nonce\s*=\s*str\s*\(", auth_text)) or bool(
        re.search(r"[\"']nonce[\"']\s*:\s*str\s*\(", auth_text)
    )
    closes_old_socket = ".close(" in before_connect
    resets_old_socket = bool(re.search(r"self\._ws\s*=\s*None", before_connect))
    reconnect_warning = "Reconnect attempt" in base_text and "failed" in base_text
    missing_close_reset = bool(reconnect) and not (closes_old_socket and resets_old_socket)
    return {
        "nonce_integer_signature": nonce_int,
        "nonce_string_signature": nonce_string,
        "reconnect_function_found": bool(reconnect),
        "reconnect_closes_old_socket_before_connect": closes_old_socket,
        "reconnect_resets_old_socket_before_connect": resets_old_socket,
        "reconnect_missing_close_reset_signature": missing_close_reset,
        "reconnect_warning_signature": reconnect_warning,
        "legacy_sdk_reconnect_bug_signature": bool(nonce_int or missing_close_reset),
    }


def inspect_dnse_runtime() -> dict[str, object]:
    spec = util.find_spec("dnse")
    dnse_version = _safe_version("dnse")
    new_sdk_version = _safe_version("dnse-sdk-openapi")
    websockets_version = _safe_version("websockets")
    module_origin = str(spec.origin) if spec and spec.origin else None
    package_root: Path | None = None
    if module_origin:
        origin = Path(module_origin).resolve()
        package_root = origin.parent if origin.name == "__init__.py" else origin.parent

    files: list[dict[str, object]] = []
    text_by_name: dict[str, str] = {}
    if package_root and package_root.is_dir():
        wanted_names = {"_base_stream.py", "_stream_auth.py", "connection.py", "client.py", "auth.py"}
        for path in sorted(package_root.rglob("*.py")):
            if path.name not in wanted_names:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = path.relative_to(package_root).as_posix()
            files.append({"path": rel, "sha256": _sha256(path), "size": path.stat().st_size})
            text_by_name[rel] = text

    signatures = detect_legacy_stream_signatures(text_by_name)
    return {
        "python": sys.version.split()[0],
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "dnse_distribution_version": dnse_version,
        "dnse_sdk_openapi_distribution_version": new_sdk_version,
        "dnse_module_origin": module_origin,
        "websockets_version": websockets_version,
        "candidate_stream_source_files": files,
        "signatures": signatures,
        "canonical_runtime_has_legacy_dnse_0_5_0": dnse_version == "0.5.0",
        "canonical_runtime_has_new_openapi_sdk": new_sdk_version is not None,
    }


def _safe_endpoint_value(key: str, value: object) -> object:
    lowered = key.lower()
    if any(secret in lowered for secret in ("secret", "token", "api_key", "apikey", "credential", "account_no")):
        return "<redacted>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value) if isinstance(value, str) else value
        if isinstance(text, str) and len(text) > 300:
            return text[:300] + "..."
        return text
    if isinstance(value, Mapping):
        return {str(k): _safe_endpoint_value(str(k), v) for k, v in value.items() if len(str(k)) <= 80}
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    return type(value).__name__


def sample_realtime_endpoint(url: str, *, samples: int = 5, interval: float = 0.4) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index in range(max(samples, 0)):
        started = time.monotonic()
        try:
            req = urlrequest.Request(url, method="GET", headers={"Accept": "application/json"})
            with urlrequest.urlopen(req, timeout=3.0) as response:
                raw = response.read(1024 * 1024)
                status = int(response.status)
            try:
                payload = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                payload = {"non_json_body_sha256": hashlib.sha256(raw).hexdigest(), "body_bytes": len(raw)}
            if isinstance(payload, Mapping):
                safe = {str(k): _safe_endpoint_value(str(k), v) for k, v in payload.items()}
                top_keys = sorted(str(k) for k in payload.keys())
            else:
                safe = {"payload_type": type(payload).__name__}
                top_keys = []
            result.append({
                "sample": index + 1,
                "http_status": status,
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 2),
                "top_level_keys": top_keys,
                "safe_payload": safe,
            })
        except (OSError, urlerror.URLError, TimeoutError) as exc:
            result.append({
                "sample": index + 1,
                "http_status": None,
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 2),
                "error": f"{type(exc).__name__}:{exc}",
            })
        if index + 1 < samples:
            time.sleep(max(interval, 0.0))
    return result


def run_rest_smoke(system_root: Path) -> dict[str, object]:
    system_src = system_root / "src"
    if str(system_src) not in sys.path:
        sys.path.insert(0, str(system_src))
    try:
        from vn_quant_local.data_sources import test_dnse_connection
        raw = test_dnse_connection()
    except Exception as exc:  # network/runtime diagnostics are part of the audit
        return {"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}
    market = raw.get("market_data") if isinstance(raw, Mapping) else {}
    portfolio = raw.get("portfolio") if isinstance(raw, Mapping) else {}
    sdk = raw.get("sdk") if isinstance(raw, Mapping) else {}
    return {
        "status": raw.get("status"),
        "market_data": {
            "status": market.get("status") if isinstance(market, Mapping) else None,
            "row_count": market.get("row_count") if isinstance(market, Mapping) else None,
            "latest_day": market.get("latest_day") if isinstance(market, Mapping) else None,
        },
        "portfolio": {
            "status": portfolio.get("status") if isinstance(portfolio, Mapping) else None,
            "account_count": portfolio.get("account_count") if isinstance(portfolio, Mapping) else None,
        },
        "sdk_version": sdk.get("version") if isinstance(sdk, Mapping) else None,
        "credential_source": raw.get("credential_source"),
    }


def _endpoint_has_unhealthy_state(samples: list[dict[str, object]]) -> bool:
    negative_words = {"failed", "error", "disconnected", "unhealthy", "reconnecting", "stale", "down"}
    for sample in samples:
        if sample.get("http_status") != 200:
            return True
        payload = sample.get("safe_payload")
        if not isinstance(payload, Mapping):
            continue
        text = json.dumps(payload, ensure_ascii=False).lower()
        if any(word in text for word in negative_words):
            return True
    return False


def build_audit(
    repo_root: Path,
    system_root: Path,
    *,
    realtime_url: str | None,
    endpoint_samples: int,
    probe_rest: bool,
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    system_root = system_root.resolve()
    runtime = inspect_dnse_runtime()
    local_matches = scan_local_realtime(repo_root, system_root)
    endpoint = sample_realtime_endpoint(realtime_url, samples=endpoint_samples) if realtime_url else []
    rest = run_rest_smoke(system_root) if probe_rest else {"status": "NOT_RUN"}

    api_realtime_matches = [
        item for item in local_matches if "API_REALTIME" in item.marker_lines
    ]
    local_dirty_or_untracked = any((not item.tracked) or item.dirty for item in api_realtime_matches)
    signatures = runtime.get("signatures") if isinstance(runtime.get("signatures"), Mapping) else {}
    legacy_bug = bool(signatures.get("legacy_sdk_reconnect_bug_signature"))
    rest_ok = rest.get("status") in {"SUCCESS", "PARTIAL"}
    endpoint_unstable = _endpoint_has_unhealthy_state(endpoint) if endpoint else False

    conclusion = {
        "localhost_realtime_http_alive": bool(endpoint) and all(x.get("http_status") == 200 for x in endpoint),
        "rest_connectivity_ok": rest_ok,
        "legacy_sdk_reconnect_bug_signature": legacy_bug,
        "local_realtime_implementation_present": bool(api_realtime_matches),
        "local_realtime_implementation_untracked_or_dirty": local_dirty_or_untracked,
        "endpoint_reports_or_exhibits_unhealthy_state": endpoint_unstable,
        "rest_ok_ws_unstable": bool(rest_ok and (endpoint_unstable or legacy_bug)),
        "migration_recommended": bool(legacy_bug or local_dirty_or_untracked),
        "recommended_architecture": (
            "ISOLATED_DNSE_OPENAPI_WEBSOCKET_SIDECAR_KEEP_CANONICAL_REST_UNCHANGED"
            if legacy_bug else "DIAGNOSE_BEFORE_MIGRATION"
        ),
        "live_order_ready": False,
    }
    return {
        "schema_version": "v85_dnse_realtime_connectivity_audit_v1",
        "audit_version": AUDIT_VERSION,
        "status": "SUCCESS",
        "runtime": runtime,
        "local_realtime_source_matches": [asdict(x) for x in local_matches],
        "realtime_endpoint_samples": endpoint,
        "rest_smoke": rest,
        "conclusion": conclusion,
        "safety": {
            "packages_installed_or_upgraded": False,
            "web_files_modified": False,
            "orders_sent": False,
            "trading_token_requested": False,
            "credentials_emitted": False,
            "live_order_ready": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--system-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--realtime-url", default="http://127.0.0.1:8787/api/realtime")
    parser.add_argument("--endpoint-samples", type=int, default=5)
    parser.add_argument("--probe-rest", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args(argv)
    try:
        report = build_audit(
            args.repo_root,
            args.system_root,
            realtime_url=args.realtime_url or None,
            endpoint_samples=args.endpoint_samples,
            probe_rest=args.probe_rest,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps(report["conclusion"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
