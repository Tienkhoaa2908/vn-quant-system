"""Pipeline StandardScaler + LogisticRegression duoc fit rieng theo fold."""
from __future__ import annotations

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def tao_pipeline(*, C: float, solver: str, max_iter: int, class_weight: None, seed: int) -> Pipeline:
    return Pipeline([
        ("standard_scaler", StandardScaler(with_mean=True, with_std=True)),
        ("logistic_regression", LogisticRegression(
            penalty="l2",
            solver=solver,
            max_iter=max_iter,
            class_weight=class_weight,
            C=C,
            random_state=seed,
        )),
    ])
