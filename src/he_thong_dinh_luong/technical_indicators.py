"""Dependency-free technical indicators computed from canonical OHLCV.

These indicators are calculated locally so the same formulas can be used in live
portfolio analysis, walk-forward validation and backtests. They are descriptive
features, not investment recommendations.
"""
from __future__ import annotations

from math import isfinite, sqrt
from statistics import fmean, pstdev
from typing import Mapping, Sequence


def _number(value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError("INDICATOR_NUMERIC_INVALID") from None
    if not isfinite(result):
        raise ValueError("INDICATOR_NUMERIC_INVALID")
    return result


def _series(rows: Sequence[object], name: str) -> list[float]:
    output: list[float] = []
    for row in rows:
        if isinstance(row, Mapping):
            value = row.get(name)
        else:
            value = getattr(row, name, None)
        output.append(_number(value))
    return output


def _ema(values: Sequence[float], window: int) -> list[float]:
    if window <= 0 or not values:
        return []
    alpha = 2.0 / (window + 1.0)
    output = [float(values[0])]
    for value in values[1:]:
        output.append(alpha * float(value) + (1.0 - alpha) * output[-1])
    return output


def _return(values: Sequence[float], window: int) -> float | None:
    if len(values) <= window or values[-window - 1] <= 0:
        return None
    return values[-1] / values[-window - 1] - 1.0


def _ma(values: Sequence[float], window: int) -> float | None:
    return fmean(values[-window:]) if len(values) >= window else None


def _rsi(values: Sequence[float], window: int = 14) -> float | None:
    if len(values) < window + 1:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = fmean(gains[:window])
    average_loss = fmean(losses[:window])
    for gain, loss in zip(gains[window:], losses[window:]):
        average_gain = ((window - 1) * average_gain + gain) / window
        average_loss = ((window - 1) * average_loss + loss) / window
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def _atr(high: Sequence[float], low: Sequence[float], close: Sequence[float], window: int = 14) -> float | None:
    if len(close) < window + 1:
        return None
    true_ranges = [
        max(high[index] - low[index], abs(high[index] - close[index - 1]), abs(low[index] - close[index - 1]))
        for index in range(1, len(close))
    ]
    value = fmean(true_ranges[:window])
    for current in true_ranges[window:]:
        value = ((window - 1) * value + current) / window
    return value


def _obv(close: Sequence[float], volume: Sequence[float]) -> list[float]:
    if not close:
        return []
    output = [0.0]
    for index in range(1, len(close)):
        direction = 1.0 if close[index] > close[index - 1] else -1.0 if close[index] < close[index - 1] else 0.0
        output.append(output[-1] + direction * volume[index])
    return output


def compute_indicators(rows: Sequence[object]) -> dict[str, object]:
    """Compute an auditable indicator snapshot from ordered OHLCV rows."""
    if not rows:
        raise ValueError("INDICATOR_ROWS_EMPTY")
    close = _series(rows, "close")
    high = _series(rows, "high")
    low = _series(rows, "low")
    volume = _series(rows, "volume")
    if any(value <= 0 for value in close + high + low) or any(value < 0 for value in volume):
        raise ValueError("INDICATOR_OHLCV_INVALID")
    for index in range(len(close)):
        if high[index] < max(close[index], low[index]) or low[index] > min(close[index], high[index]):
            raise ValueError("INDICATOR_OHLC_INVARIANT_INVALID")

    ma20, ma60, ma120, ma250 = (_ma(close, window) for window in (20, 60, 120, 250))
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd_series = [left - right for left, right in zip(ema12, ema26)]
    macd_signal_series = _ema(macd_series, 9)
    macd = macd_series[-1] if len(close) >= 26 else None
    macd_signal = macd_signal_series[-1] if len(close) >= 34 else None
    macd_hist = macd - macd_signal if macd is not None and macd_signal is not None else None

    bollinger_mid = ma20
    bollinger_std = pstdev(close[-20:]) if len(close) >= 20 else None
    bollinger_width = (
        4.0 * bollinger_std / bollinger_mid
        if bollinger_mid is not None and bollinger_std is not None and bollinger_mid > 0
        else None
    )
    bollinger_position = (
        (close[-1] - (bollinger_mid - 2.0 * bollinger_std)) / (4.0 * bollinger_std)
        if bollinger_mid is not None and bollinger_std is not None and bollinger_std > 0
        else None
    )

    atr14 = _atr(high, low, close, 14)
    atr14_pct = atr14 / close[-1] if atr14 is not None and close[-1] > 0 else None
    lowest14 = min(low[-14:]) if len(low) >= 14 else None
    highest14 = max(high[-14:]) if len(high) >= 14 else None
    stochastic14 = (
        100.0 * (close[-1] - lowest14) / (highest14 - lowest14)
        if lowest14 is not None and highest14 is not None and highest14 > lowest14
        else None
    )
    obv = _obv(close, volume)
    obv_change20 = (
        (obv[-1] - obv[-21]) / max(fmean(volume[-20:]) * 20.0, 1.0)
        if len(obv) >= 21
        else None
    )
    volume_ratio20 = volume[-1] / fmean(volume[-20:]) if len(volume) >= 20 and fmean(volume[-20:]) > 0 else None
    high52 = max(high[-250:]) if len(high) >= 250 else max(high)
    drawdown52 = close[-1] / high52 - 1.0 if high52 > 0 else None

    trend_votes = []
    for average in (ma20, ma60, ma120, ma250):
        if average is not None:
            trend_votes.append(1.0 if close[-1] > average else 0.0)
    returns = {window: _return(close, window) for window in (20, 60, 120, 250)}
    positive_returns = [1.0 if value is not None and value > 0 else 0.0 for value in returns.values() if value is not None]
    trend_score = fmean(trend_votes + positive_returns) if trend_votes or positive_returns else 0.0

    warnings: list[str] = []
    if len(close) < 250:
        warnings.append("INSUFFICIENT_HISTORY_MA250")
    if volume_ratio20 is None:
        warnings.append("INSUFFICIENT_HISTORY_VOLUME20")
    return {
        "bar_count": len(close),
        "latest_close": close[-1],
        "return_20": returns[20],
        "return_60": returns[60],
        "return_120": returns[120],
        "return_250": returns[250],
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "ma250": ma250,
        "above_ma20": ma20 is not None and close[-1] > ma20,
        "above_ma60": ma60 is not None and close[-1] > ma60,
        "above_ma120": ma120 is not None and close[-1] > ma120,
        "above_ma250": ma250 is not None and close[-1] > ma250,
        "rsi14": _rsi(close, 14),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_hist,
        "bollinger_position20": bollinger_position,
        "bollinger_width20": bollinger_width,
        "atr14_pct": atr14_pct,
        "stochastic14": stochastic14,
        "obv_change20": obv_change20,
        "volume_ratio20": volume_ratio20,
        "drawdown_52week": drawdown52,
        "trend_score": trend_score,
        "warnings": warnings,
    }
