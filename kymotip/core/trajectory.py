"""輪郭点列の並べ替え(resort)と平滑化(LOESS / 周期移動平均)。

`resort()` は python_trajectory.ipynb のロジックをそのまま移植した O(n^2) の
貪欲最近傍連結アルゴリズム。ImageJの Outline のような順序を持たない点集合を
連結された経路に変換するために使う。
"""
from __future__ import annotations

import numpy as np


def resort(x, y, d):
    """順序のない点集合 (x, y) を、距離閾値 d 以内の最近傍点を辿って並べ替える。

    python_trajectory.ipynb の resort() を忠実に移植したもの。
    """
    x = np.array(x)
    y = np.array(y)

    xr = np.zeros_like(x)
    yr = np.zeros_like(y)
    xr[0] = x[0]
    yr[0] = y[0]

    hashxy = np.zeros_like(x)
    hashxy[0] = -1

    p = 1
    for i in range(1, len(x)):
        min_dist = float("inf")
        k = 0
        for j in range(len(x)):
            if hashxy[j] == 0:
                tmp = np.linalg.norm([x[j] - xr[p - 1], y[j] - yr[p - 1]])
                if tmp <= min_dist and tmp <= d:
                    min_dist = tmp
                    k = j
        if k > 0:
            xr[p] = x[k]
            yr[p] = y[k]
            hashxy[k] = -1
            p += 1

    return xr[:p], yr[:p]


def smooth_loess(xr, yr, degree, fraction, wraparound_points=50):
    """周期的な輪郭に対応するため両端を wraparound_points 分だけ延長してから
    LOESS平滑化し、元の長さにトリムして返す(notebookのロジックを踏襲)。
    """
    from loess.loess_1d import loess_1d

    extended_x = np.concatenate([xr, xr[:wraparound_points]])
    extended_y = np.concatenate([yr, yr[:wraparound_points]])

    _, smoothed_x, _ = loess_1d(np.arange(len(extended_x)), extended_x, degree=degree, frac=fraction)
    _, smoothed_y, _ = loess_1d(np.arange(len(extended_y)), extended_y, degree=degree, frac=fraction)

    return smoothed_x[: len(xr)], smoothed_y[: len(yr)]


def cyclic_moving_average(data, window_size):
    """周期的データ用の移動平均(notebookのロジックをそのまま移植)。"""
    data = np.asarray(data)
    extended = np.concatenate((data[-(window_size - 1):], data, data[: window_size - 1]))
    smoothed = np.convolve(extended, np.ones(window_size) / window_size, mode="valid")
    return smoothed[window_size // 2 : -(window_size // 2)]


def smooth_moving_average(xr, yr, window_size):
    return cyclic_moving_average(xr, window_size), cyclic_moving_average(yr, window_size)
