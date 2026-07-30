"""Public entrypoint cho forward prediction LightGBM."""
from .du_doan_tien_phuong_contract import Metrics, Row, REGIME_FEATURES, STOCK_RANK_FEATURES, _load_verified_input
from .du_doan_tien_phuong_features import _average_percentile, _split_history
from .du_doan_tien_phuong_runner import _champion, main, run_forward_prediction

__all__ = [
    "Metrics", "Row", "REGIME_FEATURES", "STOCK_RANK_FEATURES",
    "_average_percentile", "_champion", "_load_verified_input", "_split_history",
    "main", "run_forward_prediction",
]

if __name__ == "__main__":
    raise SystemExit(main())
