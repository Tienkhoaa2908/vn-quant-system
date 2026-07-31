"""Model adapters for the VN Quant Model Lab.

Heavy libraries are lazy imports.  Production dependencies remain small while a
workstation can opt into LightGBM, XGBoost and PyTorch with explicit version
pins.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from typing import Callable, Mapping, Sequence

from .model_lab_core import BASE_MODELS
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row
from .nghien_cuu_moc_4.du_doan_tien_phuong_features import (
    _group_sizes,
    _matrix,
    _metrics,
    _relevance,
)
from .portfolio_weighting import reference_scores

Predictor = Callable[[Sequence[Row], Sequence[Row], Sequence[Row], int], list[float]]


@dataclass(frozen=True)
class ModelSpec:
    name: str
    family: str
    dependency: str | None
    description: str


MODEL_SPECS: Mapping[str, ModelSpec] = {
    "momentum_baseline": ModelSpec(
        "momentum_baseline", "rules", None,
        "Momentum 12-1 baseline; no fitting.",
    ),
    "robust_technical_ensemble_v1": ModelSpec(
        "robust_technical_ensemble_v1", "rules", None,
        "Deterministic multi-signal technical reference score.",
    ),
    "ridge_ranker": ModelSpec(
        "ridge_ranker", "linear", "sklearn",
        "Regularized linear rank regression on cross-sectional features.",
    ),
    "hist_gradient_boosting_ranker": ModelSpec(
        "hist_gradient_boosting_ranker", "tree", "sklearn",
        "Regularized histogram gradient boosting regression used as a rank score.",
    ),
    "lightgbm_ranker": ModelSpec(
        "lightgbm_ranker", "learning_to_rank", "lightgbm",
        "LambdaRank/LambdaMART grouped by signal date.",
    ),
    "xgboost_ranker": ModelSpec(
        "xgboost_ranker", "learning_to_rank", "xgboost",
        "XGBoost LambdaMART rank:ndcg grouped by signal date.",
    ),
    "torch_pairwise_mlp": ModelSpec(
        "torch_pairwise_mlp", "deep_learning", "torch",
        "Small CPU pairwise MLP with deterministic training and early stopping.",
    ),
}


def model_availability(names: Sequence[str]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for name in names:
        spec = MODEL_SPECS.get(name)
        if spec is None:
            result[name] = {"available": False, "reason": "MODEL_NOT_REGISTERED"}
            continue
        dependency = spec.dependency
        available = dependency is None or importlib.util.find_spec(dependency) is not None
        result[name] = {
            "available": available,
            "family": spec.family,
            "dependency": dependency,
            "description": spec.description,
            "reason": None if available else f"DEPENDENCY_MISSING:{dependency}",
        }
    return result


def _numpy_matrix(rows: Sequence[Row]):
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    raw, names = _matrix(rows)
    return np.asarray(raw, dtype=float), names


def _rank_target(rows: Sequence[Row]):
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    relevance = _relevance(rows)
    return np.asarray([value / 4.0 for value in relevance], dtype=float)


def _predict_momentum(
    _train: Sequence[Row], _validation: Sequence[Row], test: Sequence[Row], _seed: int,
) -> list[float]:
    return [float(row.features["dong_luong_12_1"]) for row in test]


def _predict_robust(
    _train: Sequence[Row], _validation: Sequence[Row], test: Sequence[Row], _seed: int,
) -> list[float]:
    scores, _, _ = reference_scores(test)
    return [float(value) for value in scores]


def _predict_ridge(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    del seed
    try:
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("SKLEARN_NOT_INSTALLED") from exc
    fit_rows = tuple(train) + tuple(validation)
    train_x, _ = _numpy_matrix(fit_rows)
    train_y = _rank_target(fit_rows)
    test_x, _ = _numpy_matrix(test)
    model = make_pipeline(StandardScaler(), Ridge(alpha=20.0, fit_intercept=True))
    model.fit(train_x, train_y)
    return [float(value) for value in model.predict(test_x)]


def _predict_hist_gb(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
    except ImportError as exc:
        raise ValueError("SKLEARN_NOT_INSTALLED") from exc
    fit_rows = tuple(train) + tuple(validation)
    train_x, _ = _numpy_matrix(fit_rows)
    train_y = _rank_target(fit_rows)
    test_x, _ = _numpy_matrix(test)
    model = HistGradientBoostingRegressor(
        learning_rate=0.035,
        max_iter=220,
        max_leaf_nodes=15,
        max_depth=4,
        min_samples_leaf=50,
        l2_regularization=10.0,
        early_stopping=False,
        random_state=seed,
    )
    model.fit(train_x, train_y)
    return [float(value) for value in model.predict(test_x)]


def _predict_lightgbm(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    try:
        from lightgbm import LGBMRanker
    except ImportError as exc:
        raise ValueError("LIGHTGBM_NOT_INSTALLED") from exc
    fit_rows = tuple(train) + tuple(validation)
    train_x, _ = _numpy_matrix(fit_rows)
    train_y = _relevance(fit_rows)
    test_x, _ = _numpy_matrix(test)
    model = LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=260,
        learning_rate=0.03,
        max_depth=4,
        num_leaves=15,
        min_child_samples=60,
        reg_lambda=10.0,
        feature_fraction=0.8,
        random_state=seed,
        n_jobs=1,
        verbosity=-1,
        deterministic=True,
        force_col_wise=True,
    )
    model.fit(train_x, train_y, group=_group_sizes(fit_rows))
    return [float(value) for value in model.predict(test_x)]


def _qid(rows: Sequence[Row]):
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    result: list[int] = []
    current = None
    group = -1
    for row in rows:
        if row.ngay != current:
            group += 1
            current = row.ngay
        result.append(group)
    return np.asarray(result, dtype=int)


def _predict_xgboost(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    try:
        from xgboost import XGBRanker
    except ImportError as exc:
        raise ValueError("XGBOOST_NOT_INSTALLED") from exc
    fit_rows = tuple(train) + tuple(validation)
    train_x, _ = _numpy_matrix(fit_rows)
    train_y = _relevance(fit_rows)
    test_x, _ = _numpy_matrix(test)
    model = XGBRanker(
        objective="rank:ndcg",
        n_estimators=240,
        learning_rate=0.03,
        max_depth=3,
        min_child_weight=20.0,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=10.0,
        reg_alpha=0.1,
        tree_method="hist",
        lambdarank_pair_method="mean",
        lambdarank_num_pair_per_sample=4,
        random_state=seed,
        n_jobs=1,
        verbosity=0,
    )
    model.fit(train_x, train_y, qid=_qid(fit_rows), verbose=False)
    return [float(value) for value in model.predict(test_x)]


def _pair_indexes(rows: Sequence[Row], relevance: Sequence[int], max_pairs_per_day: int = 512):
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    by_day: dict[object, list[int]] = {}
    for index, row in enumerate(rows):
        by_day.setdefault(row.ngay, []).append(index)
    left: list[int] = []
    right: list[int] = []
    for indexes in by_day.values():
        pairs = [
            (high, low)
            for high in indexes
            for low in indexes
            if relevance[high] > relevance[low]
        ]
        if len(pairs) > max_pairs_per_day:
            step = len(pairs) / max_pairs_per_day
            pairs = [pairs[min(int(position * step), len(pairs) - 1)] for position in range(max_pairs_per_day)]
        left.extend(high for high, _ in pairs)
        right.extend(low for _, low in pairs)
    if not left:
        raise ValueError("TORCH_PAIRWISE_NO_VALID_PAIRS")
    return np.asarray(left, dtype=int), np.asarray(right, dtype=int)


def _train_torch(
    rows: Sequence[Row],
    *,
    seed: int,
    epochs: int,
):
    try:
        import numpy as np
        import torch
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("TORCH_OR_SKLEARN_NOT_INSTALLED") from exc
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    raw_x, _ = _numpy_matrix(rows)
    scaler = StandardScaler()
    x = scaler.fit_transform(raw_x).astype("float32")
    relevance = _relevance(rows)
    target = np.asarray([value / 4.0 for value in relevance], dtype="float32")
    left, right = _pair_indexes(rows, relevance)

    class PairwiseMLP(torch.nn.Module):
        def __init__(self, width: int) -> None:
            super().__init__()
            self.network = torch.nn.Sequential(
                torch.nn.Linear(width, 64),
                torch.nn.LayerNorm(64),
                torch.nn.GELU(),
                torch.nn.Dropout(0.10),
                torch.nn.Linear(64, 32),
                torch.nn.LayerNorm(32),
                torch.nn.GELU(),
                torch.nn.Dropout(0.05),
                torch.nn.Linear(32, 1),
            )

        def forward(self, value):
            return self.network(value).squeeze(-1)

    model = PairwiseMLP(x.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=2e-3)
    x_tensor = torch.from_numpy(x)
    target_tensor = torch.from_numpy(target)
    left_tensor = torch.from_numpy(left)
    right_tensor = torch.from_numpy(right)
    for _ in range(max(1, epochs)):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        scores = model(x_tensor)
        pair_loss = torch.nn.functional.softplus(
            -(scores[left_tensor] - scores[right_tensor])
        ).mean()
        point_loss = torch.nn.functional.smooth_l1_loss(torch.sigmoid(scores), target_tensor)
        loss = pair_loss + 0.05 * point_loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
        optimizer.step()
    model.eval()
    return model, scaler


def _torch_predict(model, scaler, rows: Sequence[Row]) -> list[float]:
    try:
        import torch
    except ImportError as exc:
        raise ValueError("TORCH_NOT_INSTALLED") from exc
    raw_x, _ = _numpy_matrix(rows)
    transformed = scaler.transform(raw_x).astype("float32")
    with torch.no_grad():
        values = model(torch.from_numpy(transformed)).cpu().numpy()
    return [float(value) for value in values]


def _predict_torch(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    # Select training duration on the strictly prior validation block.
    candidate_epochs = (40, 80, 140)
    best: tuple[float, int] | None = None
    for epochs in candidate_epochs:
        model, scaler = _train_torch(train, seed=seed, epochs=epochs)
        validation_scores = _torch_predict(model, scaler, validation)
        rank_ic = _metrics(validation, validation_scores, min(10, len(validation))).mean_rank_ic
        key = (rank_ic, -epochs)
        if best is None or key > (best[0], -best[1]):
            best = (rank_ic, epochs)
    assert best is not None
    # Refit on all information available before the test date using the selected
    # epoch count; test labels remain unseen.
    fit_rows = tuple(train) + tuple(validation)
    model, scaler = _train_torch(fit_rows, seed=seed + 1, epochs=best[1])
    return _torch_predict(model, scaler, test)


PREDICTORS: Mapping[str, Predictor] = {
    "momentum_baseline": _predict_momentum,
    "robust_technical_ensemble_v1": _predict_robust,
    "ridge_ranker": _predict_ridge,
    "hist_gradient_boosting_ranker": _predict_hist_gb,
    "lightgbm_ranker": _predict_lightgbm,
    "xgboost_ranker": _predict_xgboost,
    "torch_pairwise_mlp": _predict_torch,
}


def predict_model(
    name: str,
    *,
    train_rows: Sequence[Row],
    validation_rows: Sequence[Row],
    test_rows: Sequence[Row],
    seed: int,
    overrides: Mapping[str, Predictor] | None = None,
) -> list[float]:
    if name not in BASE_MODELS:
        raise ValueError(f"MODEL_LAB_MODEL_NOT_SUPPORTED:{name}")
    predictor = (overrides or {}).get(name) or PREDICTORS[name]
    values = predictor(train_rows, validation_rows, test_rows, seed)
    if len(values) != len(test_rows):
        raise ValueError(f"MODEL_LAB_MODEL_LENGTH_MISMATCH:{name}")
    if any(not isinstance(value, (int, float)) for value in values):
        raise ValueError(f"MODEL_LAB_MODEL_NONNUMERIC:{name}")
    return [float(value) for value in values]
