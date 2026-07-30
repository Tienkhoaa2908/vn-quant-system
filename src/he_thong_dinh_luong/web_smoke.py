"""Khoi dong web local that va kiem tra /healthz cung trang goc qua HTTP."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(url: str, *, timeout: float, marker: str | None = None) -> str:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:  # noqa: S310 - localhost only
                body = response.read().decode("utf-8", errors="replace")
                if response.status != 200:
                    last_error = f"HTTP_{response.status}"
                elif marker is not None and marker not in body:
                    last_error = f"MARKER_MISSING:{marker}"
                else:
                    return body
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}:{exc}"
        time.sleep(0.25)
    raise RuntimeError(f"WEB_SMOKE_TIMEOUT:{url}:{last_error}")


def _stop(process: subprocess.Popen[str]) -> str:
    if process.poll() is None:
        process.terminate()
    try:
        output, _ = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate(timeout=5)
    return output or ""


def run(*, repo_root: Path, timeout: float = 45.0) -> dict[str, object]:
    repo_root = Path(repo_root).resolve()
    port = _free_port()
    with tempfile.TemporaryDirectory(prefix="vn_quant_web_smoke_") as tmp:
        data_root = Path(tmp) / "data"
        command = (
            sys.executable,
            "-m",
            "he_thong_dinh_luong.giao_dien_web",
            "--repo-root",
            str(repo_root),
            "--data-root",
            str(data_root),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-show-browser",
        )
        environment = os.environ.copy()
        environment.update({
            "PYTHONPATH": str(repo_root / "src"),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "NO_PROXY": "*",
        })
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        failed = False
        try:
            _wait(f"http://127.0.0.1:{port}/healthz", timeout=timeout, marker='"status":"ok"')
            root_body = _wait(
                f"http://127.0.0.1:{port}/",
                timeout=timeout,
                marker="VN Quant Local Console",
            )
            if "Internal Server Error" in root_body:
                raise RuntimeError("WEB_SMOKE_ROOT_500_BODY")
            return {"status": "SUCCESS", "port": port, "root_bytes": len(root_body.encode("utf-8"))}
        except Exception:
            failed = True
            raise
        finally:
            output = _stop(process)
            if failed and output:
                print(output[-12000:])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.web_smoke")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=float, default=45.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(repo_root=args.repo_root, timeout=args.timeout)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
