"""V74 publication-date point-in-time macro ablation on frozen C3.

Research only. Macro values are sourced only from official NSO public archives.
A macro release becomes visible only on/after its publication date. Frozen C3
ranking/components/labels are unchanged; V74 changes exposure only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from html import unescape
import json
import math
from pathlib import Path
import re
from statistics import fmean, median
from typing import Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from . import c3_factor_health_regime_v73 as v73
from . import deep_portfolio_backtest_v70 as v70

SCHEMA_VERSION = "macro_pit_ablation_v74"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
SOFT_EXPOSURE = 0.50
SIGNFLIP_SAMPLES = 10_000
BOOTSTRAP_SAMPLES = 5_000
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)
START_YEAR = 2016
MIN_SERIES_MONTHS = 80
BASE_POLICY = "NO_MACRO_GATE"

NSO_ARCHIVES = (
    ("CPI", "https://www.nso.gov.vn/en/cpi/"),
    ("IIP", "https://www.nso.gov.vn/en/iip/"),
)
NSO_FALLBACK_ARCHIVES = (
    ("CPI", "https://www.nso.gov.vn/cpi-vi/"),
    ("IIP", "https://www.nso.gov.vn/iip-vi/"),
)
ALLOWED_HOSTS = {"nso.gov.vn", "www.nso.gov.vn"}


@dataclass(frozen=True)
class MacroRelease:
    series: str
    reference_month: date
    issue_day: date
    yoy_pct: float
    url: str
    response_sha256: str
    language: str
    snippet: str


@dataclass(frozen=True)
class GateSpec:
    policy_id: str
    mode: str


GATES = (
    GateSpec("MACRO_IIP3_DECEL_SOFT50", "IIP_DECEL"),
    GateSpec("MACRO_CPI3_ACCEL_SOFT50", "CPI_ACCEL"),
    GateSpec("MACRO_STAGFLATION3_SOFT50", "STAGFLATION"),
)
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = unescape(raw).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s+", "\n", text).strip()


def _normalize_num(value: str) -> float:
    return float(value.replace(",", ".").strip())


def _parse_issue_day(text: str) -> date | None:
    for pattern in (
        r"Date of issue:\s*(\d{1,2})/(\d{1,2})/(\d{4})",
        r"Ngày đăng:\s*(\d{1,2})/(\d{1,2})/(\d{4})",
    ):
        match = re.search(pattern, text, flags=re.I)
        if match:
            d, m, y = map(int, match.groups())
            return date(y, m, d)
    return None


def _parse_reference_month(text: str) -> date | None:
    for pattern in (
        r"Reference period:\s*(?:Month\s*)?(\d{1,2})/(\d{4})",
        r"Kỳ tham chiếu:\s*(?:Tháng\s*)?(\d{1,2})/(\d{4})",
    ):
        match = re.search(pattern, text, flags=re.I)
        if match:
            month, year = map(int, match.groups())
            if 1 <= month <= 12:
                return date(year, month, 1)
    head = text[:900].lower()
    for name, month in MONTHS.items():
        match = re.search(rf"\b{name}\b[^0-9]{{0,50}}(20\d{{2}})", head)
        if match:
            return date(int(match.group(1)), month, 1)
    return None


def _signed_yoy(text: str, series: str) -> tuple[float, str] | None:
    low = text.lower()
    anchors = ("consumer price index", "cpi") if series == "CPI" else (
        "industrial production index", "index of industrial production", "iip"
    )
    positions = [low.find(anchor) for anchor in anchors if low.find(anchor) >= 0]
    start = min(positions) if positions else 0
    focus = text[start:start + 2400]
    patterns = (
        r"(increased|rose|grew|decreased|fell|declined)[^.%]{0,220}?by\s+([0-9]+(?:[.,][0-9]+)?)%\s+(?:year-on-year|compared (?:to|with) the same period (?:last year|of the previous year))",
        r"(increased|rose|grew|decreased|fell|declined)[^.%]{0,300}?and\s+(?:by\s+)?([0-9]+(?:[.,][0-9]+)?)%\s+(?:year-on-year|compared (?:to|with) the same period (?:last year|of the previous year))",
    )
    for pattern in patterns:
        match = re.search(pattern, focus, flags=re.I)
        if match:
            value = _normalize_num(match.group(2))
            if match.group(1).lower() in {"decreased", "fell", "declined"}:
                value = -value
            return value, focus[max(0, match.start()-180):min(len(focus), match.end()+180)]
    same_period = re.search(
        r"(?:and\s+)?(?:by\s+)?([0-9]+(?:[.,][0-9]+)?)%\s+"
        r"(?:year-on-year|compared (?:to|with) the same period (?:last year|of the previous year))",
        focus, flags=re.I,
    )
    if same_period:
        prefix = focus[max(0, same_period.start()-280):same_period.start()].lower()
        verb_positions = {
            verb: prefix.rfind(verb)
            for verb in ("increased", "rose", "grew", "decreased", "fell", "declined")
        }
        verb = max(verb_positions, key=verb_positions.get)
        value = _normalize_num(same_period.group(1))
        if verb in {"decreased", "fell", "declined"} and verb_positions[verb] >= 0:
            value = -value
        return value, focus[max(0, same_period.start()-180):min(len(focus), same_period.end()+180)]
    match = re.search(
        r"(tăng|giảm)[^.%]{0,260}?([0-9]+(?:[.,][0-9]+)?)%\s+so với cùng kỳ(?: năm trước| năm \d{4})",
        focus, flags=re.I,
    )
    if match:
        value = _normalize_num(match.group(2))
        if match.group(1).lower() == "giảm":
            value = -value
        return value, focus[max(0, match.start()-180):min(len(focus), match.end()+180)]
    return None


def parse_release_html(*, series: str, url: str, raw: bytes, language: str) -> MacroRelease | None:
    text = _strip_html(raw.decode("utf-8", errors="replace"))
    issue = _parse_issue_day(text)
    reference = _parse_reference_month(text)
    yoy = _signed_yoy(text, series)
    if issue is None or reference is None or yoy is None:
        return None
    if reference.year < START_YEAR or issue.year < START_YEAR:
        return None
    value, snippet = yoy
    if not math.isfinite(value) or abs(value) > 100.0:
        return None
    return MacroRelease(
        series, reference, issue, value, url, sha256(raw).hexdigest(), language, snippet[:800]
    )


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"V74_UNAPPROVED_MACRO_URL:{url}")
    return url


def _http_get(url: str, timeout: int = 30) -> bytes:
    _safe_url(url)
    last: Exception | None = None
    for _attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "vn-quant-system-v74-research/1.0"})
            with urlopen(req, timeout=timeout) as response:
                data = response.read()
                if not data:
                    raise ValueError("empty response")
                return data
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last = exc
    raise RuntimeError(f"V74_NSO_FETCH_FAILED:{url}:{type(last).__name__}:{last}") from last


def _article_urls(listing_html: bytes, base: str, series: str) -> list[str]:
    text = listing_html.decode("utf-8", errors="replace")
    urls: set[str] = set()
    for href in re.findall(r"(?i)href=[\"']([^\"']+)[\"']", text):
        url = urljoin(base, unescape(href)).split("#", 1)[0]
        parsed = urlparse(url)
        if parsed.hostname not in ALLOWED_HOSTS:
            continue
        path = parsed.path.lower()
        if not (
            "/data-and-statistics/" in path
            or "/du-lieu-va-so-lieu-thong-ke/" in path
            or "/tin-tuc-thong-ke/" in path
        ):
            continue
        slug = path.rstrip("/").split("/")[-1]
        if series == "CPI" and not ("consumer-price-index" in slug or "chi-so-gia-tieu-dung" in slug):
            continue
        if series == "IIP" and not ("industrial-production" in slug or "san-xuat-cong-nghiep" in slug):
            continue
        urls.add(url)
    return sorted(urls)


def _url_year(url: str) -> int | None:
    match = re.search(r"/(20\d{2})/", urlparse(url).path)
    return int(match.group(1)) if match else None


def _crawl_archive(series: str, base_url: str, *, max_pages: int = 70) -> list[str]:
    urls: set[str] = set()
    old_pages = 0
    for page in range(1, max_pages + 1):
        url = base_url if page == 1 else base_url.rstrip("/") + f"/?paged={page}"
        found = _article_urls(_http_get(url), base_url, series)
        new = [item for item in found if item not in urls]
        urls.update(found)
        years = [year for year in (_url_year(item) for item in new) if year is not None]
        old_pages = old_pages + 1 if new and years and max(years) <= START_YEAR else 0
        if old_pages >= 2 or (page > 3 and not new):
            break
    return sorted(urls)


def _collect_language(archives: Sequence[tuple[str, str]], language: str) -> list[MacroRelease]:
    tasks: list[tuple[str, str]] = []
    for series, base in archives:
        for url in _crawl_archive(series, base):
            year = _url_year(url)
            if year is None or year >= START_YEAR:
                tasks.append((series, url))

    def one(item: tuple[str, str]) -> MacroRelease | None:
        series, url = item
        return parse_release_html(series=series, url=url, raw=_http_get(url), language=language)

    releases: list[MacroRelease] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, tasks):
            if result is not None:
                releases.append(result)
    return releases


def _dedupe_first_release(releases: Sequence[MacroRelease]) -> list[MacroRelease]:
    chosen: dict[tuple[str, date], MacroRelease] = {}
    for row in sorted(releases, key=lambda x: (x.series, x.reference_month, x.issue_day, x.url)):
        key = row.series, row.reference_month
        if key not in chosen or row.issue_day < chosen[key].issue_day:
            chosen[key] = row
    return sorted(chosen.values(), key=lambda x: (x.series, x.reference_month))


def collect_nso_macro() -> list[MacroRelease]:
    releases = _collect_language(NSO_ARCHIVES, "en")
    counts = {series: sum(row.series == series for row in releases) for series in ("CPI", "IIP")}
    if min(counts.values()) < MIN_SERIES_MONTHS:
        releases += _collect_language(NSO_FALLBACK_ARCHIVES, "vi")
    result = _dedupe_first_release(releases)
    counts = {series: sum(row.series == series for row in result) for series in ("CPI", "IIP")}
    if min(counts.values()) < MIN_SERIES_MONTHS:
        raise ValueError(f"V74_MACRO_COVERAGE_INSUFFICIENT:{counts}")
    return result


def _release_rows(releases: Sequence[MacroRelease]) -> list[dict[str, object]]:
    return [{
        "series": row.series,
        "reference_month": row.reference_month.isoformat(),
        "issue_day": row.issue_day.isoformat(),
        "yoy_pct": row.yoy_pct,
        "url": row.url,
        "response_sha256": row.response_sha256,
        "language": row.language,
        "parsed_snippet": row.snippet,
    } for row in releases]


def load_macro_csv(path: Path) -> list[MacroRelease]:
    result = []
    for raw in _read_csv(path):
        result.append(MacroRelease(
            str(raw["series"]),
            date.fromisoformat(raw["reference_month"]),
            date.fromisoformat(raw["issue_day"]),
            float(raw["yoy_pct"]),
            str(raw.get("url") or "fixture://"),
            str(raw.get("response_sha256") or ""),
            str(raw.get("language") or "fixture"),
            str(raw.get("parsed_snippet") or ""),
        ))
    return _dedupe_first_release(result)


def _available(releases: Sequence[MacroRelease], series: str, signal_day: date) -> list[MacroRelease]:
    return sorted(
        (row for row in releases if row.series == series and row.issue_day <= signal_day),
        key=lambda row: (row.reference_month, row.issue_day),
    )


def macro_state(releases: Sequence[MacroRelease], signal_day: date, spec: GateSpec) -> dict[str, object]:
    cpi = _available(releases, "CPI", signal_day)
    iip = _available(releases, "IIP", signal_day)
    if len(cpi) < 4 or len(iip) < 4:
        raise ValueError(f"V74_INSUFFICIENT_PUBLISHED_MACRO_HISTORY:{signal_day}:{spec.policy_id}")
    cpi4, iip4 = cpi[-4:], iip[-4:]
    cpi_prior = fmean(row.yoy_pct for row in cpi4[:-1])
    iip_prior = fmean(row.yoy_pct for row in iip4[:-1])
    cpi_impulse = cpi4[-1].yoy_pct - cpi_prior
    iip_impulse = iip4[-1].yoy_pct - iip_prior
    if spec.mode == "IIP_DECEL":
        active = iip_impulse <= 0.0
    elif spec.mode == "CPI_ACCEL":
        active = cpi_impulse >= 0.0
    elif spec.mode == "STAGFLATION":
        active = iip_impulse <= 0.0 and cpi_impulse >= 0.0
    else:
        raise ValueError(f"V74_UNKNOWN_GATE_MODE:{spec.mode}")
    return {
        "signal_day": signal_day.isoformat(),
        "policy_id": spec.policy_id,
        "gate_mode": spec.mode,
        "latest_cpi_reference_month": cpi4[-1].reference_month.isoformat(),
        "latest_cpi_issue_day": cpi4[-1].issue_day.isoformat(),
        "latest_cpi_yoy_pct": cpi4[-1].yoy_pct,
        "cpi_prior3_yoy_mean": cpi_prior,
        "cpi_impulse_pp": cpi_impulse,
        "latest_iip_reference_month": iip4[-1].reference_month.isoformat(),
        "latest_iip_issue_day": iip4[-1].issue_day.isoformat(),
        "latest_iip_yoy_pct": iip4[-1].yoy_pct,
        "iip_prior3_yoy_mean": iip_prior,
        "iip_impulse_pp": iip_impulse,
        "gate_active": active,
        "target_exposure_if_active": SOFT_EXPOSURE,
        "publication_date_pit_enforced": True,
        "year_2026_used_for_selection": False,
        "phase": "PRE2026_PRIMARY" if signal_day <= PRIMARY_SELECTION_END else "2026_OBSERVED_SHADOW",
    }


def build_macro_snaps(*, variant_id: str, variant_dir: Path, releases: Sequence[MacroRelease]) -> tuple[dict[str, list[v70.Snap]], list[dict[str, object]]]:
    base = v70.load_snaps(variant_dir / "v67_c3_monthly_rankings.csv.gz")
    result = {BASE_POLICY: list(base)}
    states: list[dict[str, object]] = []
    for spec in GATES:
        snaps = []
        for snap in base:
            state = macro_state(releases, snap.day, spec)
            states.append({"variant_id": variant_id, **state})
            snaps.append(v70.Snap(snap.day, snap.symbols, not bool(state["gate_active"])))
        result[spec.policy_id] = snaps
    return result, states


def _pre2026_mdd(daily: Sequence[Mapping[str, object]], variant: str, allocator: str, policy: str) -> float:
    values = [
        float(row["nav_close_vnd"]) for row in daily
        if str(row.get("variant_id")) == variant
        and str(row.get("allocator")) == allocator
        and str(row.get("policy_id")) == policy
        and str(row.get("cost_scenario")) == "BASE_DNSE"
        and str(row.get("settlement_mode")) == "IMMEDIATE"
        and str(row.get("day")) <= PRIMARY_SELECTION_END.isoformat()
    ]
    if len(values) < 20:
        raise ValueError(f"V74_TOO_FEW_PRE2026_DAILY_VALUES:{variant}:{allocator}:{policy}")
    return v70._mdd(values)


def candidate_inference(monthly: Sequence[Mapping[str, object]], daily: Sequence[Mapping[str, object]], *, signflip_samples: int, bootstrap_samples: int) -> list[dict[str, object]]:
    scopes = sorted({
        (str(row["variant_id"]), str(row["allocator"])) for row in monthly
        if str(row.get("cost_scenario")) == "BASE_DNSE"
        and str(row.get("settlement_mode")) == "IMMEDIATE"
        and float(row.get("initial_capital_vnd") or 0.0) == 1_000_000_000.0
    })
    output: list[dict[str, object]] = []
    for variant, allocator in scopes:
        base: dict[tuple[str, str], Mapping[str, object]] = {}
        candidates: dict[str, dict[tuple[str, str], Mapping[str, object]]] = {}
        for row in monthly:
            if str(row.get("variant_id")) != variant or str(row.get("allocator")) != allocator:
                continue
            if str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
                continue
            if float(row.get("initial_capital_vnd") or 0.0) != 1_000_000_000.0:
                continue
            key = str(row["period_start_day"]), str(row["period_end_day"])
            policy = str(row["policy_id"])
            if policy == BASE_POLICY:
                base[key] = row
            else:
                candidates.setdefault(policy, {})[key] = row
        for policy, cmap in sorted(candidates.items()):
            paired: list[tuple[date, float]] = []
            annual_c: dict[int, float] = {}
            annual_b: dict[int, float] = {}
            for key in sorted(set(base) & set(cmap)):
                end = date.fromisoformat(key[1])
                if end > PRIMARY_SELECTION_END:
                    continue
                candidate_return = float(cmap[key]["strategy_return"])
                base_return = float(base[key]["strategy_return"])
                paired.append((end, candidate_return - base_return))
                annual_c[end.year] = annual_c.get(end.year, 1.0) * (1.0 + candidate_return)
                annual_b[end.year] = annual_b.get(end.year, 1.0) * (1.0 + base_return)
            if len(paired) < 24:
                raise ValueError(f"V74_TOO_FEW_PRE2026_PAIRED_MONTHS:{variant}:{allocator}:{policy}")
            seed = int.from_bytes(sha256(f"{variant}|{allocator}|{policy}|v74".encode()).digest()[:4], "big")
            observed, p_value = v73._signflip(paired, signflip_samples, seed)
            ci_low, ci_high = v73._bootstrap_ci(paired, bootstrap_samples, seed ^ 0x74A74)
            years = sorted(set(annual_c) & set(annual_b))
            annual_delta = [(annual_c[year] - 1.0) - (annual_b[year] - 1.0) for year in years]
            base_mdd = _pre2026_mdd(daily, variant, allocator, BASE_POLICY)
            candidate_mdd = _pre2026_mdd(daily, variant, allocator, policy)
            deltas = [value for _, value in paired]
            output.append({
                "variant_id": variant,
                "allocator": allocator,
                "policy_id": policy,
                "comparator": BASE_POLICY,
                "selection_period_end": PRIMARY_SELECTION_END.isoformat(),
                "paired_month_count": len(paired),
                "block_count": len({v73._block_key(day) for day, _ in paired}),
                "mean_monthly_return_delta": observed,
                "median_monthly_return_delta": median(deltas),
                "positive_month_delta_rate": sum(value > 0.0 for value in deltas) / len(deltas),
                "bootstrap_ci025": ci_low,
                "bootstrap_ci975": ci_high,
                "signflip_two_sided_p": p_value,
                "pre2026_year_count": len(years),
                "positive_annual_delta_rate": sum(value > 0.0 for value in annual_delta) / len(annual_delta),
                "mean_annual_return_delta": fmean(annual_delta),
                "pre2026_base_mdd": base_mdd,
                "pre2026_candidate_mdd": candidate_mdd,
                "pre2026_mdd_improvement": candidate_mdd - base_mdd,
                "year_2026_used_for_selection": False,
                "publication_date_pit_enforced": True,
            })
    v73._bh(output)
    for row in output:
        row["diagnostic_watchlist_gate_passed"] = bool(
            float(row["mean_monthly_return_delta"]) > 0.0
            and float(row["bh_fdr_q"]) < 0.10
            and float(row["bootstrap_ci025"]) > 0.0
            and float(row["positive_annual_delta_rate"]) >= 0.60
            and float(row["pre2026_mdd_improvement"]) >= -0.02
        )
    return output


def _shadow_2026(annual: Sequence[Mapping[str, object]], monthly: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    annual_map: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for row in annual:
        try:
            if int(float(row["year"])) != 2026:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        if str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
            continue
        if float(row.get("initial_capital_vnd") or 0) != 1_000_000_000.0:
            continue
        annual_map[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))] = row
    monthly_map: dict[tuple[str, str, str, str], Mapping[str, object]] = {}
    for row in monthly:
        if str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
            continue
        if float(row.get("initial_capital_vnd") or 0) != 1_000_000_000.0:
            continue
        start = str(row.get("period_start_day"))
        if start.startswith("2026-"):
            monthly_map[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]), start[:7])] = row
    output = []
    for (variant, allocator, policy), row in sorted(annual_map.items()):
        base = annual_map.get((variant, allocator, BASE_POLICY))
        if base is None:
            continue
        april = monthly_map.get((variant, allocator, policy, "2026-04"))
        base_april = monthly_map.get((variant, allocator, BASE_POLICY, "2026-04"))
        output.append({
            "variant_id": variant,
            "allocator": allocator,
            "policy_id": policy,
            "strategy_return": float(row["strategy_return"]),
            "benchmark_return": float(row["benchmark_return"]),
            "alpha_arithmetic": float(row["alpha_arithmetic"]),
            "policy_minus_base_2026_return": float(row["strategy_return"]) - float(base["strategy_return"]),
            "april_2026_return": float(april["strategy_return"]) if april else None,
            "april_2026_policy_minus_base": (
                float(april["strategy_return"]) - float(base_april["strategy_return"])
                if april and base_april else None
            ),
            "used_for_selection": False,
            "status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        })
    return output


def _audit_baseline(v70_output: Path, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    old: dict[tuple[str, str, str, str, float], Mapping[str, object]] = {}
    for row in _read_csv(v70_output / "v70_backtest_summary.csv"):
        if str(row.get("strategy_id")) not in {"C3_EQ_ALWAYS", "C3_INVOL_ALWAYS"}:
            continue
        allocator = "EQUAL" if str(row["strategy_id"]) == "C3_EQ_ALWAYS" else "INVOL60"
        key = (
            str(row["variant_id"]), allocator, str(row["settlement_mode"]),
            str(row["cost_scenario"]), float(row["initial_capital_vnd"]),
        )
        old[key] = row
    compared = 0
    max_return = max_cagr = max_mdd = 0.0
    for row in rows:
        if str(row.get("policy_id")) != BASE_POLICY:
            continue
        key = (
            str(row["variant_id"]), str(row["allocator"]), str(row["settlement_mode"]),
            str(row["cost_scenario"]), float(row["initial_capital_vnd"]),
        )
        reference = old.get(key)
        if reference is None:
            continue
        compared += 1
        max_return = max(max_return, abs(float(row["total_return"]) - float(reference["total_return"])))
        max_cagr = max(max_cagr, abs(float(row["cagr"]) - float(reference["cagr"])))
        max_mdd = max(max_mdd, abs(float(row["max_drawdown_daily"]) - float(reference["max_drawdown_daily"])))
    if compared < 24 or max(max_return, max_cagr, max_mdd) > 1e-10:
        raise ValueError(f"V74_BASELINE_RECONSTRUCTION_DRIFT:{compared}:{max_return}:{max_cagr}:{max_mdd}")
    return {
        "compared_summary_count": compared,
        "max_total_return_error": max_return,
        "max_cagr_error": max_cagr,
        "max_mdd_error": max_mdd,
    }


def analyze(*, v68_output: Path, v70_output: Path, store: Path, output_dir: Path, macro_releases: Sequence[MacroRelease] | None = None, signflip_samples: int = SIGNFLIP_SAMPLES, bootstrap_samples: int = BOOTSTRAP_SAMPLES) -> dict[str, object]:
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V74_V68_VARIANTS_MISSING")
    v70_report = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if v70_report.get("status") != "SUCCESS" or v70_report.get("champion_model") != CHAMPION_MODEL:
        raise ValueError("V74_V70_BASELINE_CONTRACT_INVALID")
    releases = _dedupe_first_release(list(macro_releases) if macro_releases is not None else collect_nso_macro())
    counts = {series: sum(row.series == series for row in releases) for series in ("CPI", "IIP")}
    if min(counts.values()) < MIN_SERIES_MONTHS:
        raise ValueError(f"V74_MACRO_COVERAGE_INSUFFICIENT:{counts}")

    snap_maps: dict[str, dict[str, list[v70.Snap]]] = {}
    state_rows: list[dict[str, object]] = []
    symbols: set[str] = set()
    for variant_dir in sorted(path for path in variants_root.iterdir() if path.is_dir()):
        built, states = build_macro_snaps(variant_id=variant_dir.name, variant_dir=variant_dir, releases=releases)
        snap_maps[variant_dir.name] = built
        state_rows.extend(states)
        for snap in built[BASE_POLICY]:
            symbols.update(snap.symbols)
    if not symbols:
        raise ValueError("V74_NO_SYMBOLS")
    market = v70.load_market(store, symbols)

    summary: list[dict[str, object]] = []
    monthly: list[dict[str, object]] = []
    annual: list[dict[str, object]] = []
    rolling: list[dict[str, object]] = []
    daily: list[dict[str, object]] = []
    ledger: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    capital_rows: list[dict[str, object]] = []
    exposures = {BASE_POLICY: 1.0, **{spec.policy_id: SOFT_EXPOSURE for spec in GATES}}
    for variant, policies in sorted(snap_maps.items()):
        for policy_id, snaps in policies.items():
            for allocator in ("EQUAL", "INVOL60"):
                exposure = exposures[policy_id]
                for cost in v70.COSTS:
                    spec = v70.Strategy(f"V74_{policy_id}_{allocator}", allocator, exposure)
                    result = v70.simulate(market, snaps, spec, cost, 1_000_000_000.0, variant)
                    summary += v73._decorate([result["summary"]], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    monthly += v73._decorate(result["periods"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    annual += v73._decorate(result["annual"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    rolling += v73._decorate(result["rolling"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    if cost.name == "BASE_DNSE":
                        daily += v73._decorate(result["daily"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                        ledger += v73._decorate(result["ledger"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                        missing += v73._decorate(result["missing"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                t2_spec = v70.Strategy(f"V74_{policy_id}_{allocator}_T2", allocator, exposure, "T2_NO_ADVANCE")
                t2 = v70.simulate(market, snaps, t2_spec, v70.COSTS[1], 1_000_000_000.0, variant)
                summary += v73._decorate([t2["summary"]], variant=variant, policy_id=policy_id, allocator=allocator, settlement="T2_NO_ADVANCE", cost_scenario="BASE_DNSE", capital=1_000_000_000.0)
                for capital in CAPITALS:
                    capital_spec = v70.Strategy(f"V74_{policy_id}_{allocator}_CAP", allocator, exposure)
                    capital_result = v70.simulate(market, snaps, capital_spec, v70.COSTS[1], capital, variant)
                    capital_rows += v73._decorate([capital_result["summary"]], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario="BASE_DNSE", capital=capital)

    baseline = _audit_baseline(v70_output, summary)
    inference = candidate_inference(monthly, daily, signflip_samples=signflip_samples, bootstrap_samples=bootstrap_samples)
    shadow = _shadow_2026(annual, monthly)
    cost_drag = v73._cost_drag(summary)
    watchlist = [row for row in inference if bool(row["diagnostic_watchlist_gate_passed"])]

    output_dir.mkdir(parents=True, exist_ok=True)
    v73._write_csv(output_dir / "v74_macro_release_history.csv", _release_rows(releases))
    v73._write_csv(output_dir / "v74_macro_state.csv", state_rows)
    v73._write_csv(output_dir / "v74_backtest_summary.csv", summary)
    v73._write_csv(output_dir / "v74_monthly_returns.csv", monthly)
    v73._write_csv(output_dir / "v74_annual_returns.csv", annual)
    v73._write_csv(output_dir / "v74_rolling_alpha.csv", rolling)
    v73._write_csv(output_dir / "v74_candidate_inference.csv", inference)
    v73._write_csv(output_dir / "v74_2026_shadow.csv", shadow)
    v73._write_csv(output_dir / "v74_cost_drag.csv", cost_drag)
    v73._write_csv(output_dir / "v74_capital_sensitivity.csv", capital_rows)
    v73._write_csv(output_dir / "v74_missing_price_events.csv", missing)
    v73._write_gz(output_dir / "v74_daily_equity_base.csv.gz", daily)
    v73._write_gz(output_dir / "v74_trade_ledger_base.csv.gz", ledger)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "research_only": True,
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "ranking_changed": False,
        "components_changed": False,
        "c3_training_label": "CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE",
        "macro_included": True,
        "macro_source": "OFFICIAL_NSO_PUBLIC_ARCHIVES",
        "macro_series": ["CPI_YOY", "IIP_YOY"],
        "macro_release_count": counts,
        "publication_date_pit_enforced": True,
        "first_release_per_reference_month": True,
        "candidate_gates": [
            {"policy_id": gate.policy_id, "mode": gate.mode, "risk_exposure": SOFT_EXPOSURE}
            for gate in GATES
        ],
        "primary_candidate_selection_end": PRIMARY_SELECTION_END.isoformat(),
        "year_2026_used_for_candidate_selection": False,
        "year_2026_status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        "signflip_samples": signflip_samples,
        "bootstrap_samples_ci_only": bootstrap_samples,
        "multiple_testing": "BH_FDR_WITHIN_VARIANT_AND_ALLOCATOR",
        "baseline_reconstruction_audit": baseline,
        "diagnostic_watchlist": watchlist,
        "diagnostic_watchlist_count": len(watchlist),
        "allocators": ["EQUAL", "INVOL60"],
        "cost_scenarios": [cost.name for cost in v70.COSTS],
        "capital_sensitivity_vnd": list(CAPITALS),
        "t2_no_advance_sensitivity": True,
        "portfolio_engine_reused": "deep_portfolio_backtest_v70",
        "profit_reporting": {"costs_included": True, "equity_curve_output": "v74_daily_equity_base.csv.gz"},
        "limitations": [
            "Macro hypotheses were designed after historical C3 review and are not pristine independent holdouts.",
            "Only official NSO first-release CPI/IIP publication-date data are used; no SBV series are added in V74.",
            "2026 is excluded from candidate inference and reported only as observed stress.",
            "PIT HOSE, price-basis/corporate-action and PIT-sector gates remain unresolved for canonical HOSE claims.",
            "Modeled costs/fixed slippage are research assumptions rather than exact market impact.",
        ],
        "promotion_authorized": False,
        "automatic_live_orders_allowed": False,
    }
    (output_dir / "v74_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", required=True, type=Path)
    parser.add_argument("--v70-output", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--macro-csv", type=Path, default=None)
    parser.add_argument("--signflip-samples", type=int, default=SIGNFLIP_SAMPLES)
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    args = parser.parse_args(argv)
    releases = load_macro_csv(args.macro_csv) if args.macro_csv else None
    report = analyze(
        v68_output=args.v68_output,
        v70_output=args.v70_output,
        store=args.store,
        output_dir=args.output_dir,
        macro_releases=releases,
        signflip_samples=args.signflip_samples,
        bootstrap_samples=args.bootstrap_samples,
    )
    print(json.dumps({
        "status": report["status"],
        "diagnostic_watchlist_count": report["diagnostic_watchlist_count"],
        "publication_date_pit_enforced": report["publication_date_pit_enforced"],
        "promotion_authorized": report["promotion_authorized"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
