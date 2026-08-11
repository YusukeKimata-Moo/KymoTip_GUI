import numpy as np

from kymotip.core.trajectory import cyclic_moving_average, resort


def test_resort_reorders_shuffled_circle_points():
    theta = np.linspace(0, 2 * np.pi, 50, endpoint=False)
    x = 10 * np.cos(theta)
    y = 10 * np.sin(theta)

    rng = np.random.default_rng(0)
    order = rng.permutation(len(theta))
    x_shuffled, y_shuffled = x[order], y[order]

    xr, yr = resort(x_shuffled, y_shuffled, d=3)

    # Every consecutive pair in the resorted output should be close together,
    # i.e. resort() has re-chained the shuffled points into a contiguous path.
    dists = np.hypot(np.diff(xr), np.diff(yr))
    assert len(xr) > len(theta) * 0.9
    assert dists.max() < 3


def test_cyclic_moving_average_preserves_length_and_smooths():
    data = np.array([0, 10, 0, 10, 0, 10, 0, 10.0])
    smoothed = cyclic_moving_average(data, window_size=3)
    assert len(smoothed) == len(data)
    assert smoothed.std() < data.std()
