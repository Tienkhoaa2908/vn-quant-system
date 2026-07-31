"""Public entrypoint for forward prediction."""
from .du_doan_tien_phuong_contract import Metrics, Row, REGIME_FEATURES, STOCK_RANK_FEATURES, _load_verified_input
from .du_doan_tien_phuong_features import _average_percentile, _split_history
from .du_doan_tien_phuong_runner import main, run_forward_prediction


def _champion(challenger: Metrics, momentum: Metrics) -> tuple[str, dict[str, bool]]:
    """Compatibility gate retained for the original LightGBM contract tests."""
    turnover_limit = min(1.0, 1.5 * max(momentum.mean_set_turnover, 0.01))
    checks = {
        "rank_ic_positive": challenger.mean_rank_ic > 0.0,
        "rank_ic_beats_momentum": challenger.mean_rank_ic > momentum.mean_rank_ic,
        "top_k_return_beats_momentum": challenger.top_k_relative_return > momentum.top_k_relative_return,
        "precision_not_worse": challenger.precision_at_k >= momentum.precision_at_k,
        "turnover_within_limit": challenger.mean_set_turnover <= turnover_limit,
    }
    return ("lightgbm_ranker" if all(checks.values()) else "momentum_baseline", checks)


__all__ = [
    "Metrics", "Row", "REGIME_FEATURES", "STOCK_RANK_FEATURES",
    "_average_percentile", "_champion", "_load_verified_input", "_split_history",
    "main", "run_forward_prediction",
]

if __name__ == "__main__":
    raise SystemExit(main())
