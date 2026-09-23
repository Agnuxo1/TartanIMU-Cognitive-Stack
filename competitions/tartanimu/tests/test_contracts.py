from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from competitions.tartanimu.src.contracts import (
    AVE_ZERO_NORMALIZER,
    ATE20_ZERO_NORMALIZER,
    assert_group_disjoint,
    assign_group_folds,
    macro_ave,
    tartanimu_score,
    validate_imu_windows,
)


def test_zero_reference_score_is_one() -> None:
    assert tartanimu_score(AVE_ZERO_NORMALIZER, ATE20_ZERO_NORMALIZER) == pytest.approx(1.0)


def test_macro_ave_weights_platforms_equally() -> None:
    truth = np.zeros((5, 3))
    pred = np.array([[1, 0, 0], [1, 0, 0], [0, 2, 0], [0, 0, 3], [0, 0, 3]], dtype=float)
    assert macro_ave(truth, pred, ["car", "car", "dog", "drone", "drone"]) == pytest.approx((1 + 2 + 3) / 3)


def test_imu_contract_requires_200_by_6() -> None:
    validate_imu_windows(np.zeros((4, 200, 6), dtype=np.float32))
    with pytest.raises(ValueError, match="200, 6"):
        validate_imu_windows(np.zeros((4, 100, 6), dtype=np.float32))


def test_imu_contract_rejects_nonfinite() -> None:
    imu = np.zeros((200, 6), dtype=np.float32)
    imu[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        validate_imu_windows(imu)


def test_trajectory_folds_are_deterministic_and_whole() -> None:
    frame = pd.DataFrame({"trajectory_id": ["b", "a", "b", "c", "a", "d"]})
    folds = assign_group_folds(frame, n_splits=2)
    assert folds.tolist() == [1, 0, 1, 0, 0, 1]
    assert folds.groupby(frame["trajectory_id"]).nunique().max() == 1


def test_trajectory_leakage_is_rejected() -> None:
    assert_group_disjoint(
        pd.DataFrame({"trajectory_id": ["a"]}),
        pd.DataFrame({"trajectory_id": ["b"]}),
    )
    with pytest.raises(ValueError, match="trajectory leakage"):
        assert_group_disjoint(
            pd.DataFrame({"trajectory_id": ["a", "b"]}),
            pd.DataFrame({"trajectory_id": ["b", "c"]}),
        )
