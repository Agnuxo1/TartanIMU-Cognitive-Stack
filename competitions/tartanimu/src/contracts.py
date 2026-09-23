"""Leakage-safe contracts for the TartanIMU challenge.

This module deliberately stops before model training: the complete authorized
competition data is not present locally. It implements only deterministic
input/split/score contracts that can be tested with synthetic data.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


AVE_ZERO_NORMALIZER = 0.7356384388
ATE20_ZERO_NORMALIZER = 3.1160277267
EXPECTED_SAMPLE_RATE_HZ = 200
EXPECTED_WINDOW_SAMPLES = 200
EXPECTED_IMU_CHANNELS = 6
EXPECTED_PLATFORMS = ("car", "dog", "drone", "human")


def tartanimu_score(ave: float, ate20: float) -> float:
    """Return the official dimensionless score; lower is better."""

    values = np.asarray([ave, ate20], dtype=np.float64)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("AVE and ATE20 must be finite non-negative values")
    return float(0.6 * ave / AVE_ZERO_NORMALIZER + 0.4 * ate20 / ATE20_ZERO_NORMALIZER)


def macro_ave(y_true: np.ndarray, y_pred: np.ndarray, platform: Iterable[str]) -> float:
    """Compute AVE macro-averaged over the platform labels supplied.

    The official evaluation supplies all four platforms. This helper averages
    each provided platform equally and therefore cannot silently weight a
    data-rich platform by its number of windows.
    """

    truth = np.asarray(y_true, dtype=np.float64)
    pred = np.asarray(y_pred, dtype=np.float64)
    groups = np.asarray(list(platform), dtype=object)
    if truth.shape != pred.shape or truth.ndim != 2 or truth.shape[1] != 3:
        raise ValueError(f"velocity arrays must both have shape (n, 3), got {truth.shape} and {pred.shape}")
    if len(groups) != len(truth):
        raise ValueError("platform length differs from velocity rows")
    if not np.isfinite(truth).all() or not np.isfinite(pred).all():
        raise ValueError("velocities must be finite")
    platform_errors = []
    for name in sorted(set(groups.tolist())):
        mask = groups == name
        if not mask.any():
            continue
        platform_errors.append(float(np.linalg.norm(pred[mask] - truth[mask], axis=1).mean()))
    if not platform_errors:
        raise ValueError("at least one platform is required")
    return float(np.mean(platform_errors))


def validate_imu_windows(imu: np.ndarray, *, sample_rate_hz: int = EXPECTED_SAMPLE_RATE_HZ) -> None:
    """Validate raw IMU tensor shape and SI-signal finiteness.

    The challenge contract is one-second, 200-sample, six-channel windows at
    200 Hz. This does not inspect or infer platform identity.
    """

    array = np.asarray(imu)
    if array.ndim not in (2, 3):
        raise ValueError(f"IMU must be 2D or 3D, got {array.shape}")
    if array.shape[-2:] != (EXPECTED_WINDOW_SAMPLES, EXPECTED_IMU_CHANNELS):
        raise ValueError(f"expected (..., 200, 6), got {array.shape}")
    if sample_rate_hz != EXPECTED_SAMPLE_RATE_HZ:
        raise ValueError(f"expected {EXPECTED_SAMPLE_RATE_HZ} Hz, got {sample_rate_hz}")
    if not np.issubdtype(array.dtype, np.number) or not np.isfinite(array).all():
        raise ValueError("IMU must be numeric and finite")


def assign_group_folds(index: pd.DataFrame, *, n_splits: int = 5, group_column: str = "trajectory_id") -> pd.Series:
    """Assign complete trajectories to deterministic folds without leakage."""

    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    if group_column not in index:
        raise KeyError(f"missing group column: {group_column}")
    groups = sorted(index[group_column].dropna().unique().tolist())
    if len(groups) < n_splits:
        raise ValueError(f"need at least {n_splits} groups, got {len(groups)}")
    mapping = {group: position % n_splits for position, group in enumerate(groups)}
    return index[group_column].map(mapping).astype("int64")


def assert_group_disjoint(train_index: pd.DataFrame, valid_index: pd.DataFrame, *, group_column: str = "trajectory_id") -> None:
    """Raise if a trajectory occurs in both train and validation."""

    if group_column not in train_index or group_column not in valid_index:
        raise KeyError(f"missing group column: {group_column}")
    overlap = sorted(
        set(train_index[group_column].dropna().tolist())
        & set(valid_index[group_column].dropna().tolist())
    )
    if overlap:
        raise ValueError(f"trajectory leakage detected: {overlap}")
